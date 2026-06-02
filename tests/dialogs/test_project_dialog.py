from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import QtCore, QtWidgets

from rascal2.dialogs.startup_dialog import (
    PROJECT_FILES,
    ImportProjectDialog,
    LoadDialog,
    NewProjectDialog,
    StartupDialog,
)


class MockParentWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.presenter = MagicMock()
        self.toolbar = self.addToolBar("ToolBar")
        self.toolbar.setEnabled(False)
        self.show_project_dialog = MagicMock()


view = MockParentWindow()


@pytest.mark.parametrize(
    ("dialog", "num_widgets"),
    (
        [NewProjectDialog, 1],
        [LoadDialog, 1],
        [ImportProjectDialog, 1],
    ),
)
def test_project_dialog_initial_state(dialog, num_widgets):
    """Tests that each dialog has expected initial state."""
    with patch("rascal2.dialogs.startup_dialog.update_recent_projects", return_value=[]):
        project_dialog = dialog(view)

    assert project_dialog.isModal()
    assert project_dialog.minimumWidth() == 700

    if project_dialog == NewProjectDialog:
        assert project_dialog.project_name.placeholderText() == "Enter project name"
        assert project_dialog.project_name_label.text() == "Project Name:"
        assert project_dialog.project_name_error.text() == "Project name needs to be specified."
        assert project_dialog.project_name_error.isHidden()

    if dialog == ImportProjectDialog:
        assert project_dialog.project_folder.placeholderText() == "Select RasCAL-1 file"
        assert project_dialog.project_folder_label.text() == "RasCAL-1 file:"
    else:
        assert project_dialog.project_folder.placeholderText() == "Select project folder"
        assert project_dialog.project_folder_label.text() == "Project Folder:"
    assert project_dialog.project_folder_error.isHidden()
    assert project_dialog.project_folder.isReadOnly()


@pytest.mark.parametrize("name, name_valid", [("", False), ("Project", True)])
@pytest.mark.parametrize("folder, folder_valid", [("", False), ("Folder", True)])
@pytest.mark.parametrize("other_folder_error", [True, False])
def test_create_button(name, name_valid, folder, folder_valid, other_folder_error):
    """Tests project creation on the NewProjectDialog class."""
    project_dialog = NewProjectDialog(view)
    mock_create = view.presenter.create_project = MagicMock()

    create_button = project_dialog.layout().itemAt(2).layout().itemAt(0).widget()

    project_dialog.project_name.setText(name)
    project_dialog.project_folder.setText(folder)
    if other_folder_error:
        project_dialog.set_folder_error("Folder error!!")

    create_button.click()

    if name_valid and folder_valid and not other_folder_error:
        mock_create.assert_called_once()
    else:
        mock_create.assert_not_called()


@pytest.mark.parametrize("widget", [LoadDialog, ImportProjectDialog])
@pytest.mark.parametrize("folder, folder_valid", [("", False), ("Folder", True)])
@pytest.mark.parametrize("other_folder_error", [True, False])
@patch("rascal2.dialogs.startup_dialog.Worker", autospec=True)
def test_load_button(worker_mock, widget, folder, folder_valid, other_folder_error):
    """Tests project loading on the LoadDialog and LoadR1Dialog class."""
    with patch("rascal2.dialogs.startup_dialog.update_recent_projects", return_value=[]):
        project_dialog = widget(view)
    if widget == LoadDialog:
        load_button = project_dialog.tabs.widget(0).layout().itemAt(2).layout().itemAt(0).widget()
    else:
        load_button = project_dialog.layout().itemAt(2).layout().itemAt(0).widget()

    project_dialog.project_folder.setText(folder)
    if other_folder_error:
        project_dialog.set_folder_error("Folder error!!")

    load_button.click()
    if folder_valid and not other_folder_error:
        worker_mock.call.assert_called()
    else:
        worker_mock.call.assert_not_called()


@patch.object(StartupDialog, "reject")
def test_cancel_button(mock_reject):
    """Tests cancel button on the StartupDialog class."""
    view.startup_dlg = None
    project_dialog = StartupDialog(view)

    cancel_button = project_dialog.layout().itemAt(2).layout().itemAt(0).widget()

    cancel_button.click()
    mock_reject.assert_called_once()


def test_folder_selector():
    """Tests the folder selector and verification on the StartupDialog class."""
    project_dialog = StartupDialog(view)
    project_dialog.folder_selector = MagicMock()
    project_dialog.folder_selector.return_value = "/test/folder/path"

    # When folder verification succeeds.
    project_dialog.open_folder_selector()

    assert project_dialog.project_folder.text() == "/test/folder/path"
    assert project_dialog.project_folder_error.isHidden()

    # When folder verification fails.
    def error(folder_path):
        raise ValueError("Folder verification error!")

    project_dialog.verify_folder = error

    project_dialog.open_folder_selector()

    assert project_dialog.project_folder.text() == ""
    assert project_dialog.project_folder_error.text() == "Folder verification error!"
    assert not project_dialog.project_folder_error.isHidden()


@pytest.mark.parametrize(
    "recent",
    [
        [],
        ["proj1"],
        ["proj1", "proj2"],
        ["proj1", "proj2", "proj3", "proj4", "proj5", "proj6", "invisible1", "invisible2"],
    ],
)
def test_recent_projects(recent):
    """Tests that the Recent Projects list is as expected."""
    with patch("rascal2.dialogs.startup_dialog.update_recent_projects", return_value=recent):
        project_dialog = LoadDialog(view)

    if recent:
        # size of recent list capped at 6
        assert project_dialog.recent_list_widget.count() == min(len(recent), 6)

        for i, label in enumerate(recent[0:6]):
            assert label in project_dialog.recent_list_widget.item(i).data(QtCore.Qt.ItemDataRole.UserRole)


@pytest.mark.parametrize(
    "contents, has_project",
    [
        ([], False),
        (["file.txt, settings.json", "data/"], False),
        (["controls.json", "project.json"], True),
        (["controls.json", "project.json", "logs/", "plots/", ".otherfile"], True),
    ],
)
def test_verify_folder(contents, has_project):
    """Test folder verification for create and load widgets."""
    with TemporaryDirectory() as tmp:
        for file in contents:
            Path(tmp, file).touch()

        if has_project:
            LoadDialog(view).verify_folder(tmp)
            with pytest.raises(ValueError, match="Folder already contains a project."):
                NewProjectDialog(view).verify_folder(tmp)
        else:
            NewProjectDialog(view).verify_folder(tmp)
            with pytest.raises(ValueError, match="No project found in this folder."):
                LoadDialog(view).verify_folder(tmp)


@patch("rascal2.dialogs.startup_dialog.Worker", autospec=True)
def test_load_recent_project(worker_mock):
    """Ensure that the load_recent_project slot loads the project it was initialised with."""
    dialog = LoadDialog(view)

    with TemporaryDirectory() as tmp:
        for file in PROJECT_FILES:
            Path(tmp, file).touch()

        dialog.load_project()
        worker_mock.call.assert_not_called()
        dialog.project_folder.setText(tmp)
        dialog.project_folder_error.hide()
        dialog.load_project()
        worker_mock.call.assert_called_once()
