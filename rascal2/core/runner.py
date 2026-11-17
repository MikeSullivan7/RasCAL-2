"""QObject for running rat."""

import os
import sys
from dataclasses import dataclass
from io import StringIO
from logging import INFO
from multiprocessing import Event, Process, Queue

import ratapi as rat
from PyQt6 import QtCore

from rascal2.config import MatlabHelper, get_matlab_engine


def clear_queue(queue):
    """Clear multiprocessing queue.

    Parameters
    ----------
    queue : multiprocessing.Queue
        multiprocessing queue.
    """
    queue.put(None)
    for _ in iter(queue.get, None):
        pass


def is_matlab_required(project):
    """Check if the project requires MATLAB to run.

    Parameters
    ----------
    project: ratapi.Project
        A project to check for MATLAB dependency.

    Returns
    -------
    bool
        indicates project needs MATLAB to run.
    """
    files = {file.name: file.language for file in project.custom_files}
    if project.model != "standard layers":
        for contrast in project.contrasts:
            if contrast.model and files.get(contrast.model[0]) == "matlab":
                return True

    for background in project.backgrounds:
        if background.type == "function" and files.get(background.source) == "matlab":
            return True

    return False


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

        # this queue handles both progress event data and results
        self.queue = Queue()
        self.msg_queue = Queue()
        self.plot_queue = Queue()
        self.arg_queue = Queue()
        self.create_process()
        self.updated_problem = None
        self.results = None
        self.error = None
        self.events = []

    def create_process(self):
        """Create process and multiprocessing event."""
        self.go_event = Event()
        self.exit_event = Event()
        matlab_helper = MatlabHelper()
        self.process = Process(
            target=run,
            args=(
                self.queue,
                self.arg_queue,
                self.msg_queue,
                self.plot_queue,
                self.go_event,
                self.exit_event,
                matlab_helper.ready_event,
                matlab_helper.engine_output,
            ),
        )

    def set_runner_args(self, rat_inputs, display_on: bool, working_dir: str, need_matlab: bool):
        """Send arguments to the running process.

        Parameters
        ----------
        rat_inputs: tuple
            Problem and controls for the run.
        display_on: bool
            Indicates if displaying is allowed.
        working_dir: str
            working directory of the project.
        need_matlab: bool
            indicates MATLAB is needed for run.
        """
        self.clear_queues_and_events()
        self.arg_queue.put((rat_inputs, display_on, working_dir, need_matlab))

    def start(self):
        """Start the calculation."""
        if not self.process.is_alive():
            # recreate the proces if it got killed somehow
            self.create_process()
            self.process.start()
        self.go_event.set()
        self.timer.start()

    def _handle_plot_event(self):
        """Handle for plot events."""
        item = None
        while not self.plot_queue.empty():
            item = self.plot_queue.get()
        else:
            if item is not None:
                self.events.append(item)
                self.event_received.emit()

    def _handle_msg_event(self):
        """Handle for message events."""
        text = ""
        while not self.msg_queue.empty():
            item = self.msg_queue.get()
            if isinstance(item, str):
                text += item[:-1] if item.endswith("\n\n") else item
            if isinstance(item, LogData):
                if text:
                    self.events.append(text)
                    self.event_received.emit()
                    text = ""
                self.events.append(item)
                self.event_received.emit()
        if text:
            self.events.append(text)
            self.event_received.emit()

    def handle_msg_and_plot_event(self):
        """Handle for message and plot events."""
        self._handle_plot_event()
        self._handle_msg_event()

    def check_queue(self):
        """Check for new data in the queue."""
        if self.process is None or not self.process.is_alive():
            self.timer.stop()

        self.handle_msg_and_plot_event()
        self.queue.put(None)
        for item in iter(self.queue.get, None):
            if isinstance(item, tuple):
                self.updated_problem, self.results = item
                self.go_event.clear()
                self.handle_msg_and_plot_event()
                if is_empty_bayes_result(self.results):
                    self.stopped.emit()
                else:
                    self.finished.emit()
                self.timer.stop()
            elif isinstance(item, Exception):
                self.error = item
                self.go_event.clear()
                self.handle_msg_and_plot_event()
                self.stopped.emit()
                self.timer.stop()
            else:  # else, assume item is an event
                self.events.append(item)
                self.event_received.emit()

    def clear_queues_and_events(self):
        """Clear the queues and events used by the runner."""
        clear_queue(self.queue)
        clear_queue(self.arg_queue)
        clear_queue(self.msg_queue)
        clear_queue(self.plot_queue)
        self.events.clear()
        self.go_event.clear()
        self.exit_event.clear()

    def stop(self):
        """Stop the runner."""
        self.event_received.disconnect()
        if self.process.is_alive():
            self.process.kill()
        self.process = None
        self.clear_queues_and_events()


def init_matlab_engine(engine_ready, engine_output, msg_queue):
    """Initialise the Matlab engine if using a Matlab custom file and returns the engine future if available.

    Parameters
    ----------
    engine_ready : multiprocessing.Event
        An event to inform listeners that MATLAB is ready.
    engine_output : multiprocessing.Manager.list
        A list with the name of MATLAB engine instance or an exception from the MatlabHelper.
    msg_queue : multiprocessing.Queue
        A queue for messages.

    Returns
    -------
    output : matlab.engine.futureresult.FutureResult
        MATLAB engine future or Exception from MatlabHelper.
    """
    engine_future = rat.wrappers.MatlabWrapper.loader
    if engine_future is None:
        if not engine_output:
            msg_queue.put(LogData(INFO, "Attempting to start Matlab..."))

        result = get_matlab_engine(engine_ready, engine_output)
        if isinstance(result, Exception):
            raise result
        else:
            engine_future = result
            engine_future.result().cd(os.getcwd())
    return engine_future


def stop_matlab_engine(engine_future):
    """Exit the Matlab engine future if present.

    Parameters
    ----------
    engine_future : Union[matlab.engine.futureresult.FutureResult, None]
        MATLAB engine future or Exception from MatlabHelper.
    """
    if engine_future is not None:
        engine_future.result().exit()


def is_empty_bayes_result(result):
    """Check if result is an empty BayesResults.

    Parameters
    ----------
    result : Union[ratapi.outputs.Results, ratapi.outputs.BayesResults]
        The calculation results.

    Returns
    -------
    bool
        indicates result is an empty BayesResults.
    """
    return isinstance(result, rat.BayesResults) and result.chain.size == 2


def run(
    queue: Queue, arg_queue: Queue, msg_queue: Queue, plot_queue, go_event, exit_event, engine_ready, engine_output
):
    """Run RAT and put the result into the queue.

    Parameters
    ----------
    queue : Queue
        The interprocess queue for the RATRunner.
    arg_queue :
        A queue of arguments used to initialize the RAT process, passed from the Main Presenter
    msg_queue : multiprocessing.Queue
        A queue for messages.
    plot_queue : multiprocessing.Queue
        A queue for messages.
    go_event : multiprocessing.Event
        An event to inform run function to proceed.
    exit_event : multiprocessing.Event
        An event to inform run function to exit.
    engine_ready : multiprocessing.Event
        An event to inform listeners that MATLAB is ready.
    engine_output : multiprocessing.Manager.list
        A list with the name of MATLAB engine instance or an exception from the MatlabHelper.
    """
    engine_future = None
    while True:
        go_event.wait()
        if exit_event.is_set():
            stop_matlab_engine(engine_future)
            return
        rat_inputs, display, working_dir, need_matlab = arg_queue.get()
        os.chdir(working_dir)
        problem_definition, cpp_controls = rat_inputs

        if display:
            rat.events.register(rat.events.EventTypes.Message, msg_queue.put)
            rat.events.register(rat.events.EventTypes.Progress, queue.put)
            rat.events.register(rat.events.EventTypes.Plot, plot_queue.put)
            msg_queue.put(LogData(INFO, "Starting RAT"))

        try:
            sys.path.append(working_dir)
            if need_matlab:
                engine_future = init_matlab_engine(engine_ready, engine_output, queue)

            if isinstance(cpp_controls, dict):
                ipc_path = cpp_controls.pop("ipc_path")
                matlab_rat_path = cpp_controls.pop("matlab_rat_path")
                problem, results = rat.matlab.run_matlab_directly(
                    problem_definition, cpp_controls, matlab_rat_path, ipc_path, stderr=StringIO(), stdout=StringIO()
                )
                problem_definition = rat.inputs.make_problem(problem)
            else:
                problem_definition, output_results, bayes_results = rat.rat_core.RATMain(
                    problem_definition, cpp_controls
                )
                results = rat.outputs.make_results(cpp_controls.procedure, output_results, bayes_results)
        except Exception as err:
            queue.put(err)
            go_event.clear()
            continue
        finally:
            sys.path.remove(working_dir)

        if display:
            msg = "RAT run interrupted!" if is_empty_bayes_result(results) else "Finished RAT"
            msg_queue.put(LogData(INFO, msg))
            rat.events.clear()

        queue.put((problem_definition, results))
        go_event.clear()


@dataclass
class LogData:
    """Dataclass for logging data."""

    level: int
    msg: str
