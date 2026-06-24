"""QObject for running rat."""

import os
import time
from dataclasses import dataclass
from logging import INFO
from multiprocessing import Process, Queue, cpu_count, Event

import ratapi as rat
from PyQt6 import QtCore

from rascal2.config import MatlabHelper, get_matlab_engine


class RATRunner(QtCore.QObject):
    """Class for running rat."""

    event_received = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    stopped = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.check_queue)
        self.matlab_helper = MatlabHelper()
        self.num_cores = cpu_count()

        # this queue handles both event data and results
        self.queue = Queue()
        self.arg_queue = Queue()
        self.go_event = Event()
        self.exit_event = Event()
        self.processes_list_go_exit_events = [(Event(), Event()) for _ in range(self.num_cores)]
        self.rat_inputs = None
        self.procedure = None
        self.display_on = None
        self.processes_list = []
        self.refresh_process_list()
        self.process = self.processes_list.pop(0)
        self.updated_problem = None
        self.results = None
        self.error = None
        self.events = []

    def set_runner_args(self, rat_inputs, procedure, display_on: bool):
        self.arg_queue.put((rat_inputs, procedure, display_on))

    def start(self):
        """Start the calculation."""
        if not self.process.is_alive():
            if not self.processes_list:
                self.refresh_process_list()
            self.process = self.processes_list.pop(0)
            # self.process.start()
            # if self.parent:
            #     self.parent.view.terminal_widget.write("Starting RAT Runner process...")
            self.go_event, self.exit_event = self.processes_list_go_exit_events.pop(0)
            self.go_event.set()
            self.timer.start()

    def interrupt(self):
        """Interrupt the running process."""
        self.timer.stop()
        self.process.kill()
        self.stopped.emit()
        self.go_event.clear()

    def check_queue(self):
        """Check for new data in the queue."""
        if not self.process.is_alive():
            self.timer.stop()
        self.queue.put(None)
        for item in iter(self.queue.get, None):
            if isinstance(item, tuple):
                self.updated_problem, self.results = item
                self.go_event.clear()
                self.finished.emit()
            elif isinstance(item, Exception):
                self.error = item
                self.go_event.clear()
                self.stopped.emit()
            else:  # else, assume item is an event
                print(f"{item=}")
                self.events.append(item)
                self.event_received.emit()

    def refresh_process_list(self):

        self.processes_list = [
            Process(
                target=run,
                args=(
                    self.queue,
                    self.arg_queue,
                    self.matlab_helper.ready_event,
                    self.matlab_helper.engine_output,
                    self.processes_list_go_exit_events[ind][0],
                    self.processes_list_go_exit_events[ind][1]
                ),
            )
            for ind in range(self.num_cores)
        ]

    def clear_queues(self):
        self.queue.empty()
        self.arg_queue.empty()
        self.events.clear()
        self.go_event.clear()
        self.exit_event.clear()

    def start_processes(self):
        for process in self.processes_list:
            process.start()

    def stop_processes(self):
        print("stopping processes")
        self.exit_event.set()
        self.go_event.set()
        for process in self.processes_list:
            print(f"{process.is_alive()}")
        for go_event, exit_event in self.processes_list_go_exit_events:
            exit_event.set()
            go_event.set()
        for _ in range(self.queue.qsize()):
            print(self.queue.get())
        self.clear_queues()
        for process in self.processes_list:
            print(process.name)
            process.join()
            print(f"{process.is_alive()}")
            process.close()


def run(queue: Queue, arg_queue: Queue, engine_ready, engine_output, go_event, exit_event):
    """Run RAT and put the result into the queue.

    Parameters
    ----------
    queue : Queue
        The interprocess queue for the RATRunner.
    arg_queue :
        A queue of arguments used to initialize the RAT process, passed from the Main Presenter

    """
    go_event.wait()
    if exit_event.is_set():
        queue.put(LogData(INFO, "exit_event triggers"))
        return
    rat_inputs, procedure, display = arg_queue.get()
    problem_definition, cpp_controls = rat_inputs

    if display:
        rat.events.register(rat.events.EventTypes.Message, queue.put)
        rat.events.register(rat.events.EventTypes.Progress, queue.put)
        rat.events.register(rat.events.EventTypes.Plot, queue.put)
        queue.put(LogData(INFO, "Starting RAT"))

    try:
        engine_future = None
        if any([file["language"] == "matlab" for file in problem_definition.customFiles.files]):
            if not engine_output and display:
                queue.put(LogData(INFO, "Attempting to start Matlab..."))

            result = get_matlab_engine(engine_ready, engine_output)
            if display:
                queue.put(LogData(INFO, "Got Matlab engine"))
            if isinstance(result, Exception):
                raise result
            else:
                engine_future = result
                engine_future.result().cd(os.getcwd())
        problem_definition, output_results, bayes_results = rat.rat_core.RATMain(problem_definition, cpp_controls)
        if display:
            queue.put(LogData(INFO, "Creating RAT Results..."))
        results = rat.outputs.make_results(procedure, output_results, bayes_results)
        if engine_future is not None:
            engine_future.result().exit()
    except Exception as err:
        queue.put(err)
        return

    if display:
        queue.put(LogData(INFO, "Finished RAT"))
        rat.events.clear()

    queue.put((problem_definition, results))


@dataclass
class LogData:
    """Dataclass for logging data."""

    level: int
    msg: str
