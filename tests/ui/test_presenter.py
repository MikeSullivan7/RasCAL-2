"""Tests for the Presenter."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from PyQt6 import QtWidgets
from ratapi import Controls
from ratapi.events import ProgressEventData
from ratapi.inputs import ProblemDefinition

from rascal2.core.runner import LogData
from rascal2.ui.presenter import MainWindowPresenter


class MockUndoStack:
    """A mock Undo stack."""

    def __init__(self):
        self.stack = []
        self.clean = True

    def push(self, command):
        self.clean = False
        command.redo()

    def setClean(self):
        self.clean = True

    def isClean(self):
        return self.clean


class MockWindowView(QtWidgets.QMainWindow):
    """A mock MainWindowView class."""

    def __init__(self):
        super().__init__()
        self.undo_stack = MockUndoStack()
        self.controls_widget = MagicMock()
        self.project_widget = MagicMock()
        self.terminal_widget = MagicMock()
        self.plot_widget = MagicMock()
        self.handle_results = MagicMock()
        self.settings = MagicMock()
        self.get_project_folder = lambda: "new path/"
        self.windowTitle = lambda: "RasCAL2"
        self.show_message = MagicMock()


@pytest.fixture
def presenter():
    with (
        patch("rascal2.ui.presenter.LOGGER", autospec=True) as mock_log,
        patch("rascal2.ui.model.os.chdir", autospec=True),
    ):
        pr = MainWindowPresenter(MockWindowView())
        pr.runner = MagicMock()
        pr.model.controls = Controls()
        pr.model.project = MagicMock()
        pr.model.project.name = "test_name"
        pr.model.results = MagicMock()
        pr.model.save_path = "some_path/"
        pr.logger = mock_log

        yield pr


@pytest.mark.parametrize(["param", "value"], [("nSamples", 50), ("parallel", "contrasts")])
def test_set_controls_data(presenter, param, value):
    """Check that setting values are correctly propagated to the Controls object."""
    presenter.edit_controls(param, value)
    assert getattr(presenter.model.controls, param) == value


@pytest.mark.parametrize(["param", "value"], [("nSamples", "???"), ("parallel", "bad parallel setting")])
def test_controls_validation_error(presenter, param, value):
    """Test that data is not changed if invalid data is passed to set."""
    try:
        presenter.edit_controls(param, value)
    except ValidationError as err:
        with pytest.raises(ValidationError, match=f"{param}"):
            raise err
    else:
        raise AssertionError("Invalid data did not raise error!")


@patch("ratapi.inputs.make_input")
@patch("rascal2.ui.presenter.RATRunner")
def test_run_and_interrupt(mock_runner, mock_inputs, presenter):
    """Test that the runner can be started and interrupted."""
    assert presenter.model.controls._IPCFilePath == ""
    presenter.run()
    mock_inputs.assert_called_once()
    presenter.runner.start.assert_called_once()
    assert presenter.model.controls._IPCFilePath != ""

    presenter.view.show_confirm_stop_calculation_dialog = MagicMock(return_value=False)
    presenter.interrupt_terminal()
    presenter.runner.interrupt.assert_not_called()

    presenter.view.show_confirm_stop_calculation_dialog = MagicMock(return_value=True)
    presenter.runner.process.is_alive.return_value = False
    presenter.interrupt_terminal()
    presenter.runner.interrupt.assert_not_called()

    presenter.runner.process.is_alive.return_value = True
    presenter.interrupt_terminal()
    presenter.runner.interrupt.assert_called()

    with open(presenter.model.controls._IPCFilePath) as f:
        assert f.readline() == "\x00"
    presenter.model.controls.procedure = "simplex"
    presenter.interrupt_terminal()
    with open(presenter.model.controls._IPCFilePath) as f:
        assert f.readline() == "\x01"


@patch("rascal2.core.commands.SaveCalculationOutputs")
@patch("ratapi.inputs.make_problem")
def test_handle_results(mock_problem_def, mock_command, presenter):
    """Test that results are handed to the view correctly."""
    presenter.runner = MagicMock()
    presenter.runner.updated_problem = ProblemDefinition()
    presenter.runner.results = MagicMock()
    presenter.runner.results.calculationResults.sumChi = 0.04
    presenter.handle_results()

    presenter.view.handle_results.assert_called_once_with(presenter.runner.results)
    mock_command.assert_called_once()


def test_stop_run(presenter):
    """Test that log info is emitted and the run is stopped when stop_run is called."""
    presenter.runner = MagicMock()
    presenter.runner.error = None
    presenter.handle_interrupt()
    presenter.logger.info.assert_called_once_with("RAT run interrupted!")


def test_run_error(presenter):
    """Test that a critical log is emitted if stop_run is called with an error."""
    presenter.runner = MagicMock()
    presenter.runner.error = ValueError("Test error!")
    presenter.handle_interrupt()
    presenter.logger.error.assert_called_once_with("RAT run failed with exception.\n", exc_info=presenter.runner.error)


@pytest.mark.parametrize(
    ("procedure", "string"),
    [
        ("calculate", "Test message!"),
        ("simplex", "some stuff, 3443, 10.5, 9"),
        ("de", "things: 54, Best: 10.5, test... ... N: 65.3"),
    ],
)
def test_handle_message_chisquared(presenter, procedure, string):
    """Test that messages are handled correctly, including chi-squared data."""
    presenter.runner.events = [string]
    presenter.model.controls.procedure = procedure
    presenter.handle_event()
    presenter.view.terminal_widget.write.assert_called_with(string)
    if procedure in ["simplex", "de"]:
        presenter.view.controls_widget.chi_squared.setText.assert_called_with("10.5")
    else:
        presenter.view.controls_widget.chi_squared.setText.assert_not_called()


def test_handle_progress_event(presenter):
    """Test that progress events are handled correctly."""
    presenter.runner.events = [ProgressEventData()]
    presenter.handle_event()
    presenter.view.terminal_widget.update_progress.assert_called()


def test_handle_log_data(presenter):
    presenter.runner.events = [LogData(10, "Test log!")]
    presenter.handle_event()
    presenter.logger.log.assert_called_with(10, "Test log!")


@pytest.mark.parametrize("function", ["create_project", "load_project", "load_r1_project"])
def test_load_project(presenter, function):
    """All the project initialisation functions should run the corresponding model function and initialise UI."""
    end_function = MagicMock()
    setattr(presenter.model, function, MagicMock())
    presenter.model.results = None

    if function == "create_project":
        params = ("proj_name", "some_path/")
        presenter.initialise_ui = end_function
    else:
        presenter.model.project.name = "proj_name"
        params = ("some_path/",)
        presenter.quick_run = end_function

    getattr(presenter, function)(*params)

    end_function.assert_called_once()
    getattr(presenter.model, function).assert_called_once_with(*params)


@patch("rascal2.ui.presenter.update_recent_projects")
def test_save_project(recent_projects_mock, presenter):
    """Test that projects can be saved, optionally saved as a new folder."""
    presenter.model.project = MagicMock()
    presenter.model.project.name = "test_name"
    presenter.model.controls = MagicMock()
    presenter.view.project_widget.stacked_widget.currentIndex = MagicMock(return_value=0)
    presenter.save_project()
    presenter.model.project.save.assert_called_once()
    presenter.model.controls.save.assert_called_once()

    presenter.save_project(save_as=True)
    assert presenter.model.save_path == "new path/"
    assert presenter.view.undo_stack.isClean()
    assert presenter.model.project.save.call_count == 2
    assert presenter.model.controls.save.call_count == 2
    recent_projects_mock.assert_called_with("new path/")


def test_save_project_as_script(presenter):
    """Test that projects can be saved as a script, optionally saved as a new folder."""
    presenter.model.project = MagicMock()
    presenter.model.project.name = "test_name"
    presenter.model.controls = MagicMock()
    presenter.view.project_widget.stacked_widget.currentIndex = MagicMock(return_value=0)
    presenter.save_project(as_script=True)
    presenter.model.project.write_script.assert_called_once()

    presenter.save_project(as_script=True, save_as=True)
    assert presenter.view.undo_stack.isClean()
    presenter.model.project.write_script.assert_called_with(script="new path//project_script.py")

@pytest.mark.parametrize(
    ["reply", "undo_clean_state", "expected"],
    [
        ("Save", True, True),
        ("Save", False, True),
        ("Discard", True, True),
        ("Discard", False, True),
        ("Cancel", True, True),
        ("Cancel", False, False),
    ],
)
def test_ask_to_save_project(presenter, reply, undo_clean_state, expected):
    """Test whether or not to proceed with an event based on the response to the unsaved changes warning."""
    presenter.model.save_project = MagicMock()
    presenter.view.show_unsaved_dialog = MagicMock(return_value=reply)
    presenter.view.project_widget.stacked_widget.currentIndex = MagicMock(return_value=0)

    presenter.view.undo_stack.clean = undo_clean_state
    assert presenter.ask_to_save_project() is expected


@patch("rascal2.ui.presenter.write_result_to_zipped_csvs")
def test_export_fits(mock_write_result, presenter):
    """Test that results can be exported."""
    test_zip_file = "test.zip"
    presenter.view.get_save_file = MagicMock(return_value=test_zip_file)

    presenter.export_fits()
    mock_write_result.assert_called_once_with(test_zip_file, presenter.model.results)

    # If we do not return a save file, don't export
    mock_write_result.reset_mock()
    presenter.view.get_save_file = MagicMock(return_value=None)

    presenter.export_fits()
    mock_write_result.assert_not_called()

    # If there is an OSError, log the error
    error = OSError("Test Error")
    mock_write_result.side_effect = error
    presenter.view.get_save_file = MagicMock(return_value=test_zip_file)
    presenter.logger.error = MagicMock()

    presenter.export_fits()
    mock_write_result.assert_called_once_with(test_zip_file, presenter.model.results)
    presenter.logger.error.assert_called_once_with("Failed to save fits to test.zip.\n", exc_info=error)

    # If we do not have any results, don't ask for a file
    presenter.view.get_save_file.reset_mock()
    presenter.model.results = None

    presenter.export_fits()
    presenter.view.get_save_file.assert_not_called()
