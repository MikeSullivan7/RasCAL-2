"""Unit tests for the main window view."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import QtWidgets
from PyQt6.QtCore import QSettings

from rascal2.settings import MDIGeometries
from rascal2.ui.view import MainWindowView


class MockFigureCanvas(QtWidgets.QWidget):
    """A mock figure canvas."""

    def draw(*args, **kwargs):
        pass


class MockNavigationToolbar(QtWidgets.QWidget):
    """A mock navigation toolbar."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._actions = {"pan": None, "zoom": None}


@pytest.fixture
def test_view():
    """An instance of MainWindowView."""
    with (
        patch("rascal2.widgets.plot.FigureCanvasQTAgg", return_value=MockFigureCanvas()),
        patch("rascal2.widgets.plot.NavigationToolbar2QT", return_value=MockNavigationToolbar()),
        patch("rascal2.ui.presenter.RATRunner", autospec=True, return_value=MagicMock()),
    ):
        yield MainWindowView()


@pytest.mark.parametrize(
    "geometry",
    [
        (
            (1, 2, 196, 24, True),
            (1, 2, 196, 24, True),
            (1, 2, 196, 24, True),
            (1, 2, 196, 24, True),
            (1, 2, 196, 24, True),
        ),
        (
            (1, 2, 196, 24, True),
            (3, 78, 196, 24, True),
            (1, 2, 204, 66, False),
            (12, 342, 196, 24, True),
            (5, 6, 200, 28, True),
        ),
    ],
)
@patch("rascal2.ui.view.ProjectWidget.show_project_view")
@patch("rascal2.ui.view.MainWindowPresenter")
@patch("rascal2.ui.view.ControlsWidget.setup_controls")
class TestMDISettings:
    def test_reset_mdi(self, mock1, mock2, mock3, global_setting, test_view, geometry):
        """Test that resetting the MDI works."""
        test_view.setup_mdi()
        global_setting.setValue(
            "mdi_defaults",
            MDIGeometries(plots=geometry[0], project=geometry[1], terminal=geometry[2], controls=geometry[3]),
        )
        test_view.reset_mdi_layout()
        mdi_defaults = global_setting.value("mdi_defaults")
        for window in test_view.mdi.subWindowList():
            # get corresponding MDIGeometries entry for the widget
            widget_name = window.windowTitle().lower().split(" ")[-1]
            w_geom = window.geometry()
            assert getattr(mdi_defaults, widget_name) == (
                w_geom.x(),
                w_geom.y(),
                w_geom.width(),
                w_geom.height(),
                window.isMinimized(),
            )

    def test_set_mdi(self, mock1, mock2, mock3, global_setting, test_view, geometry):
        """Test that setting the MDI adds the expected object to settings."""
        test_view.setup_mdi()
        widgets_in_order = []

        for i, window in enumerate(test_view.mdi.subWindowList()):
            widgets_in_order.append(window.windowTitle().lower().split(" ")[-1])
            window.setGeometry(*geometry[i][0:4])
            if geometry[i][4] is True:
                window.showMinimized()

        test_view.save_mdi_layout()
        mdi_defaults = global_setting.value("mdi_defaults")
        for i, widget in enumerate(widgets_in_order):
            window = test_view.mdi.subWindowList()[i]
            assert getattr(mdi_defaults, widget) == (
                window.x(),
                window.y(),
                window.width(),
                window.height(),
                window.isMinimized(),
            )


def test_set_enabled(test_view):
    """Tests that the list of disabled elements are disabled on initialisation, and can be enabled."""
    for element in test_view.disabled_elements:
        assert not element.isEnabled()
    test_view.enable_elements()
    for element in test_view.disabled_elements:
        assert element.isEnabled()


@patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory")
@patch("rascal2.ui.view.get_global_settings")
@patch("rascal2.ui.presenter.RATRunner", autospec=True, return_value=MagicMock())
def test_get_project_folder(mock_runner, mock_get_global, mock_get_dir: MagicMock):
    """Test that getting a specified folder works as expected."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ini_file = Path(tmp_dir) / "settings.ini"
        global_setting = QSettings(str(ini_file), QSettings.Format.IniFormat)
        mock_get_global.return_value = global_setting

        view = MainWindowView()
        view.check_save_blacklist = MagicMock(return_value=False)
        mock_overwrite = MagicMock(return_value=True)

        tmp = tempfile.mkdtemp()
        view.presenter.create_project("test", tmp)
        mock_get_dir.return_value = tmp

        with patch.object(view, "show_confirm_dialog", new=mock_overwrite):
            assert view.get_project_folder() == tmp

        # check overwrite is triggered if project already in folder
        Path(tmp, "controls.json").touch()
        with patch.object(view, "show_confirm_dialog", new=mock_overwrite):
            assert view.get_project_folder() == tmp
        mock_overwrite.assert_called_once()

        def change_dir(*args, **kwargs):
            """Change directory so mocked save_as doesn't recurse forever."""
            mock_get_dir.return_value = "OTHERPATH"

        # check not saved if overwrite is cancelled
        # to avoid infinite recursion (which only happens because of the mock),
        # set the mock to change the directory to some other path once called
        mock_overwrite = MagicMock(return_value=False, side_effect=change_dir)

        with patch.object(view, "show_confirm_dialog", new=mock_overwrite):
            assert view.get_project_folder() == "OTHERPATH"

        mock_overwrite.assert_called_once()


@pytest.mark.parametrize("submenu_name", ["&File", "&Edit", "&Windows", "&Tools", "&Help"])
def test_menu_element_present(test_view, submenu_name):
    """Test requested menu items are present."""
    main_menu = test_view.menuBar()

    elements = main_menu.children()
    assert any(hasattr(submenu, "title") and submenu.title() == submenu_name for submenu in elements)


@pytest.mark.parametrize(
    "submenu_name, action_names_and_layout",
    [
        (
            "&File",
            [
                "&New Project",
                "",
                "&Open Project",
                "Open &RasCAL-1 Project",
                "",
                "&Save",
                "Save To &Folder...",
                "Save Project as &Script...",
                "",
                "Export Fits",
                "",
                "Settings",
                "",
                "E&xit",
            ],
        ),
        ("&Edit", ["&Undo", "&Redo", "Undo &History"]),
        ("&Windows", ["Tile Windows", "Reset to Default", "Save Current Window Positions"]),
        ("&Tools", ["Show &Sliders", "", "Clear Terminal"]),
        ("&Help", ["&About", "&Help"]),
    ],
)
def test_help_menu_actions_present(test_view, submenu_name, action_names_and_layout):
    """Test if menu actions are available and their layouts are as specified in parameterize."""
    main_menu = test_view.menuBar()
    submenus = main_menu.findChildren(QtWidgets.QMenu)
    for menu in submenus:
        if menu.title() == submenu_name:
            submenu = menu
            break
    actions = submenu.actions()
    assert len(actions) == len(action_names_and_layout)
    for action, name in zip(actions, action_names_and_layout, strict=True):
        assert action.text() == name


@patch("rascal2.ui.presenter.RATRunner", autospec=True, return_value=MagicMock())
def test_toggle_slider(mock_runner):
    mw = MainWindowView()
    with patch.object(mw, "project_widget") as project_mock:
        show_text = mw.toggle_slider_action.property("show_text")
        hide_text = mw.toggle_slider_action.property("hide_text")
        assert mw.toggle_slider_action.text() == show_text
        project_mock.show_slider_view.assert_not_called()
        project_mock.show_project_view.assert_not_called()

        mw.toggle_sliders()

        assert mw.toggle_slider_action.text() == hide_text
        project_mock.show_slider_view.assert_called_once()

        mw.toggle_sliders()
        assert mw.toggle_slider_action.text() == show_text
        project_mock.show_project_view.assert_called_once()
