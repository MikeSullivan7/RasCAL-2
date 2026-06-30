"""QObject for running rat."""

import os
from dataclasses import dataclass
from logging import INFO
from multiprocessing import Event, Process, Queue, cpu_count

import ratapi as rat
from PyQt6 import QtCore

from rascal2.config import MatlabHelper, get_matlab_engine


class RATRunner(QtCore.QObject):
    """Class for running rat."""

    event_received = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    stopped = QtCore.pyqtSignal()
    go_event = Event()
    processes_list_go_exit_events = []

    def __init__(self, parent=None, start_runners_early: bool = True, num_cores: int = cpu_count()):
        super().__init__()
        self.parent = parent
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.check_queue)
        self.matlab_helper = MatlabHelper()
        self.num_cores = num_cores
        self.start_runners_early = start_runners_early

        # this queue handles both event data and results
        self.queue = Queue()
        self.arg_queue = Queue()
        self.go_event = Event()
        self.exit_event = Event()
        self.rat_inputs = None
        self.procedure = None
        self.display_on = None
        self.processes_list = []
        self.refresh_process_list()
        self.process = None
        self.updated_problem = None
        self.results = None
        self.error = None
        self.events = []
        self.engine_future = None

    def set_runner_args(self, rat_inputs, procedure, display_on: bool):
        self.arg_queue.put((rat_inputs, procedure, display_on))
        self.rat_inputs = rat_inputs
        self.display_on = display_on

    def start(self):
        """Start the calculation."""
        self.process, (self.go_event, self.exit_event) = self.get_new_process()
        if self.engine_future is None:
            self.get_runner_matlab_engine()
        self.go_event.set()
        if not self.process.is_alive():
            self.process.start()
        self.timer.start()

    def get_new_process(self):
        if not self.processes_list:
            self.refresh_process_list()
        return self.processes_list.pop(0), self.processes_list_go_exit_events.pop(0)

    def get_runner_matlab_engine(self):
        problem_definition, cpp_controls = self.rat_inputs
        if any([file["language"] == "matlab" for file in problem_definition.customFiles.files]):
            engine_ready = (self.matlab_helper.ready_event,)
            engine_output = self.matlab_helper.engine_output
            matlab_queue = Queue()
            get_runner_matlab_engine_process = Process(
                target=run_matlab_init_engine,
                args=(matlab_queue, engine_output, engine_ready, self.display_on),
            )
            get_runner_matlab_engine_process.start()
            get_runner_matlab_engine_process.join()
            self.engine_future = self.filter_queue(matlab_queue)

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
        self.filter_queue(self.queue)

    def filter_queue(self, queue: Queue):
        queue.put(None)
        for item in iter(queue.get, None):
            if isinstance(item, tuple):
                self.updated_problem, self.results = item
                self.go_event.clear()
                self.finished.emit()
            elif isinstance(item, Exception):
                self.error = item
                self.go_event.clear()
                self.stopped.emit()
            elif isinstance(item, list):
                return item[0]
            else:  # else, assume item is an event
                self.events.append(item)
                self.event_received.emit()

    def refresh_process_list(self):
        self.processes_list_go_exit_events = [(Event(), Event()) for _ in range(self.num_cores)]
        self.processes_list = [
            Process(
                target=run,
                args=(
                    self.queue,
                    self.arg_queue,
                    self.processes_list_go_exit_events[ind][0],
                    self.processes_list_go_exit_events[ind][1],
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
        if self.start_runners_early:
            for process in self.processes_list:
                process.start()

    def stop_processes(self):
        self.exit_event.set()
        self.go_event.set()
        for go_event, exit_event in self.processes_list_go_exit_events:
            exit_event.set()
            go_event.set()
        for process in self.processes_list:
            if process.is_alive():
                process.kill()
        self.processes_list.clear()
        self.clear_queues()
        self.processes_list_go_exit_events.clear()
        self.queue.close()
        self.arg_queue.close()
        if self.engine_future is not None:
            self.engine_future.result().exit()
        self.matlab_helper.close_event.set()


def run(queue: Queue, arg_queue: Queue, go_event, exit_event):
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
        problem_definition, output_results, bayes_results = rat.rat_core.RATMain(problem_definition, cpp_controls)
        if display:
            queue.put(LogData(INFO, "Creating RAT Results..."))
        results = rat.outputs.make_results(procedure, output_results, bayes_results)
    except Exception as err:
        queue.put(err)
        return

    if display:
        queue.put(LogData(INFO, "Finished RAT"))
        rat.events.clear()

    queue.put((problem_definition, results))


def run_matlab_init_engine(queue, engine_output, engine_ready, display_on):
    """Get the engine future from the matlab engine and put in queue if successfully."""
    try:
        if not engine_output and display_on:
            queue.put(LogData(INFO, "Attempting to start Matlab..."))

        result = get_matlab_engine(engine_ready, engine_output)
        if display_on:
            queue.put(LogData(INFO, "Got Matlab engine"))
        if isinstance(result, Exception):
            raise result
        else:
            engine_future = result
            engine_future.result().cd(os.getcwd())
            queue.put([engine_future])

    except Exception as err:
        queue.put(err)
        return


@dataclass
class LogData:
    """Dataclass for logging data."""

    level: int
    msg: str
