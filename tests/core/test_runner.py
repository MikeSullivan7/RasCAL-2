"""Tests for the RATRunner class."""

import contextlib
import os
from multiprocessing import Event
from queue import Queue  # we need a non-multiprocessing queue because mocks cannot be serialised
from unittest.mock import MagicMock, patch

import pytest
import ratapi as rat

from rascal2.core.runner import LogData, RATRunner, run


def make_rat_input():
    mock = MagicMock(spec=rat.rat_core.ProblemDefinition)
    mock.customFiles.files = []
    return (mock, 1)


def make_progress_event(percent):
    event = rat.events.ProgressEventData()
    event.percent = percent
    return event


def mock_rat_main(*args, **kwargs):
    """Mock of RAT main that produces some signals."""
    rat.events.notify(rat.events.EventTypes.Progress, make_progress_event(0.2))
    rat.events.notify(rat.events.EventTypes.Progress, make_progress_event(0.5))
    rat.events.notify(rat.events.EventTypes.Message, "test message")
    rat.events.notify(rat.events.EventTypes.Message, "test message 2")
    rat.events.notify(rat.events.EventTypes.Progress, make_progress_event(0.7))
    return 1, 2, 3


def close_processes(runner):
    # Non serialised queue does not have a close attribute so have to mock it out
    if runner.process is not None:
        runner.process.join()
    runner.queue.close = MagicMock()
    runner.arg_queue.close = MagicMock()
    runner.stop_processes()


@patch("rascal2.core.runner.MatlabHelper", autospec=True)
@patch("rascal2.core.runner.Process")
@patch("rascal2.core.runner.RATRunner.get_new_process")
def test_start(mock_process_go_exit, mock_process, mock_matlab):
    """Test that `start` creates and starts a process and timer."""
    mock_matlab.return_value = MagicMock()
    mock_go = MagicMock()
    mock_process_go_exit.return_value = MagicMock(), (mock_go, MagicMock())
    runner = RATRunner(start_runners_early=False, num_processes=1)
    runner.process = None
    runner.get_runner_matlab_engine = MagicMock()
    runner.set_runner_args(make_rat_input(), "", True, os.getcwd())
    runner.start()

    mock_go.set.assert_called_once()
    assert runner.timer.isActive()

    close_processes(runner)


@patch("rascal2.core.runner.MatlabHelper", autospec=True)
@patch("rascal2.core.runner.Process")
def test_interrupt(mock_process, mock_matlab):
    """Test that `interrupt` kills the process and stops the timer."""
    mock_matlab.return_value = MagicMock()
    runner = RATRunner(start_runners_early=False, num_processes=1)
    runner.process = MagicMock()
    runner.clear_process = MagicMock()
    runner.set_runner_args([], "", True, os.getcwd())
    runner.interrupt()

    runner.process.kill.assert_called_once()
    assert not runner.timer.isActive()

    close_processes(runner)


@pytest.mark.parametrize(
    "queue_items",
    [
        ["message!"],
        ["message!", (MagicMock(spec=rat.rat_core.ProblemDefinition), MagicMock(spec=rat.outputs.Results))],
        [(MagicMock(spec=rat.rat_core.ProblemDefinition), MagicMock(spec=rat.outputs.BayesResults))],
        [make_progress_event(0.6)],
        [make_progress_event(0.5), ValueError("Runner error!")],
        ["message 1!", make_progress_event(0.4), "message 2!"],
    ],
)
@patch("rascal2.core.runner.MatlabHelper", autospec=True)
@patch("rascal2.core.runner.Process")
def test_check_queue(mock_process, mock_matlab, queue_items):
    """Test that queue data is appropriately assigned."""
    mock_matlab.return_value = MagicMock()
    runner = RATRunner(start_runners_early=False, num_processes=1)
    runner.process = MagicMock()
    runner.get_runner_matlab_engine = MagicMock()
    runner.set_runner_args([], "", True, os.getcwd())
    runner.queue = Queue()

    for item in queue_items:
        runner.queue.put(item)

    runner.check_queue()

    assert len(runner.events) == len([x for x in queue_items if not isinstance(x, (tuple, Exception))])
    for i, item in enumerate(runner.events):
        if isinstance(item, rat.events.ProgressEventData):
            assert item.percent == queue_items[i].percent
        else:
            assert item == queue_items[i]

    if isinstance(queue_items[-1], tuple):
        assert isinstance(runner.updated_problem, rat.rat_core.ProblemDefinition)
        assert isinstance(runner.results, rat.outputs.Results)
    if isinstance(queue_items[-1], Exception):
        assert isinstance(runner.error, ValueError)
        assert str(runner.error) == "Runner error!"

    close_processes(runner)


@patch("rascal2.core.runner.MatlabHelper", autospec=True)
@patch("rascal2.core.runner.Process")
def test_empty_queue(mock_process, mock_matlab):
    """Test that nothing happens if the queue is empty."""
    mock_matlab.return_value = MagicMock()
    runner = RATRunner(start_runners_early=False, num_processes=1)
    runner.process = MagicMock()
    runner.set_runner_args(make_rat_input(), "", True, os.getcwd())

    runner.check_queue()

    assert len(runner.events) == 0
    assert runner.results is None

    close_processes(runner)


@pytest.mark.parametrize("display", [True, False])
@patch("ratapi.rat_core.RATMain", new=mock_rat_main)
@patch("ratapi.outputs.make_results", new=MagicMock(spec=rat.outputs.Results))
@patch("rascal2.core.runner.LOOP_PROCESS", new=False)
def test_run(display):
    """Test that a run puts the correct items in the queue."""
    queue = Queue()
    engine_ready = Queue()
    engine_output = Queue()
    args_queue = Queue()
    args_queue.put((make_rat_input(), "", display, os.getcwd()))
    go_event, exit_event = (Event(), Event())
    go_event.set()
    go_event.clear = lambda: exit_event.set()
    with patch("rascal2.core.runner.init_matlab_engine"), patch("rascal2.core.runner.stop_matlab_engine"):
        run(queue, args_queue, go_event, exit_event, engine_ready, engine_output)

    expected_display = [
        LogData(20, "Starting RAT"),
        0.2,
        0.5,
        "test message",
        "test message 2",
        0.7,
        LogData(20, "Finished RAT"),
    ]

    while not queue.empty():
        item = queue.get()
        if isinstance(item, tuple):
            # ensure results were the last item to be added
            assert queue.empty()
        else:
            expected_item = expected_display.pop(0)
            if isinstance(item, rat.events.ProgressEventData):
                assert item.percent == expected_item
            else:
                assert item == expected_item


def test_run_error():
    """If RATMain produces an error, it should be added to the queue."""

    def erroring_ratmain(*args):
        """RATMain mock that raises an error."""
        raise ValueError("RAT Main Error!")

    with (
        patch("ratapi.rat_core.RATMain", new=erroring_ratmain),
        patch("rascal2.core.runner.init_matlab_engine"),
        patch("rascal2.core.runner.stop_matlab_engine"),
    ):
        queue = Queue()
        engine_ready = Queue()
        engine_output = Queue()
        args_queue = Queue()
        args_queue.put((make_rat_input(), "", True, os.getcwd()))
        go_event, exit_event = (Event(), Event())
        go_event.set()
        go_event.clear = lambda: exit_event.set()
        run(queue, args_queue, go_event, exit_event, engine_ready, engine_output)

    queue.put(None)
    queue_contents = list(iter(queue.get, None))
    assert len(queue_contents) == 2
    assert isinstance(queue_contents[0], LogData)
    error = queue_contents[1]
    assert isinstance(error, ValueError)
    assert str(error) == "RAT Main Error!"


@pytest.mark.parametrize("example", rat.examples.__all__)
@patch("rascal2.core.runner.LOOP_PROCESS", new=False)
def test_run_examples(example):
    """Test that the run function runs without an error on the ratapi example projects."""
    # skip convert rascal example
    if example == "convert_rascal":
        return

    # suppress RAT printing
    with open(os.devnull, "w", encoding="utf-8") as stdout, contextlib.redirect_stdout(stdout):
        project, _ = getattr(rat.examples, example)()

    rat_inputs = rat.inputs.make_input(project, rat.Controls())

    queue = Queue()
    args_queue = Queue()
    args_queue.put((rat_inputs, "calculate", False, os.getcwd()))
    engine_ready = Queue()
    engine_output = Queue()
    go_event, exit_event = (Event(), Event())
    go_event.set()
    go_event.clear = lambda: exit_event.set()
    with patch("rascal2.core.runner.init_matlab_engine"), patch("rascal2.core.runner.stop_matlab_engine"):
        run(queue, args_queue, go_event, exit_event, engine_ready, engine_output)

    output = queue.get()

    assert isinstance(output[0], rat.rat_core.ProblemDefinition)
    assert isinstance(output[1], rat.outputs.Results)


@patch("rascal2.core.runner.MatlabHelper", autospec=True)
@patch("rascal2.core.runner.Process")
@patch("rascal2.core.runner.RATRunner.get_new_process")
def test_start_reuses_process(mock_process_go_exit, mock_process, mock_matlab):
    """Test that when running `start` a second time, it will reuse the previous process."""
    mock_matlab.return_value = MagicMock()
    mock_go = MagicMock()
    mock_process_go_exit.return_value = MagicMock(), (mock_go, MagicMock())
    runner = RATRunner(start_runners_early=False, num_processes=1)
    runner.process = None
    runner.get_runner_matlab_engine = MagicMock()
    runner.get_new_process = MagicMock(return_value=(MagicMock(), (MagicMock(), MagicMock())))
    runner.set_runner_args(make_rat_input(), "", True, os.getcwd())
    runner.start()
    runner.get_new_process.assert_called_once()
    runner.start()
    runner.get_new_process.assert_called_once()
    close_processes(runner)


@patch("rascal2.core.runner.MatlabHelper", autospec=True)
@patch("rascal2.core.runner.Process")
@patch("rascal2.core.runner.RATRunner.get_new_process")
def test_interrupt_creates_new_process(mock_process_go_exit, mock_process, mock_matlab):
    """Test that when interrupting a process, it will use a new process on next run."""
    mock_matlab.return_value = MagicMock()
    mock_go = MagicMock()
    mock_process_go_exit.return_value = MagicMock(), (mock_go, MagicMock())
    runner = RATRunner(start_runners_early=False, num_processes=1)
    runner.process = None
    runner.get_runner_matlab_engine = MagicMock()
    runner.get_new_process = MagicMock(return_value=(MagicMock(), (MagicMock(), MagicMock())))
    runner.set_runner_args(make_rat_input(), "", True, os.getcwd())
    runner.start()
    runner.get_new_process.assert_called_once()
    assert runner.process is not None
    runner.interrupt()
    assert runner.process is None
    runner.start()
    assert runner.process is not None
    assert runner.get_new_process.call_count == 2
    close_processes(runner)
