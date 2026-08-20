import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6 import QtCore, QtWidgets

APP = QtWidgets.QApplication([])
GLOBAL_SETTING = None


@pytest.fixture
def qt_application():
    return APP


@pytest.fixture
def global_setting():
    return GLOBAL_SETTING


@pytest.fixture(scope="function", autouse=True)
def mock_start_processes_setting(monkeypatch):
    monkeypatch.setenv("START_PROCESSES", "False")


@pytest.fixture(scope="session", autouse=True)
def mock_setting(request):
    global GLOBAL_SETTING
    tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    ini_file = Path(tmp_dir.name) / "settings.ini"
    GLOBAL_SETTING = QtCore.QSettings(str(ini_file), QtCore.QSettings.Format.IniFormat)
    setting_patch = []
    for target in [
        "rascal2.ui.view.get_global_settings",
        "rascal2.settings.get_global_settings",
        "rascal2.dialogs.check_update_dialog.get_global_settings",
    ]:
        setting_patch.append(patch(target, return_value=GLOBAL_SETTING))
        setting_patch[-1].start()

    def teardown_mock_setting():
        global GLOBAL_SETTING
        GLOBAL_SETTING = None
        tmp_dir.cleanup()
        for target in setting_patch:
            target.stop()

    request.addfinalizer(teardown_mock_setting)


def pytest_addoption(parser):
    parser.addoption("--run-system-tests", action="store_true", default=False, help="Run GUI system tests offscreen")
    parser.addoption("--run-system-tests-show", action="store_true", default=False, help="Run GUI system tests")
    parser.addoption("--run-unit-tests", action="store_true", default=False, help="Run unit tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "system: GUI system tests")
    config.addinivalue_line("markers", "unit: unit tests")


allowed_markers = []
skipped_tests = []


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-system-tests"):
        allowed_markers.append(pytest.mark.system.mark)
        os.environ["QT_QPA_PLATFORM"] = "minimal"
    if config.getoption("--run-system-tests-show"):
        allowed_markers.append(pytest.mark.system.mark)
        os.environ["QT_QPA_PLATFORM"] = ""
    if config.getoption("--run-unit-tests") or len(allowed_markers) == 0:
        allowed_markers.append(pytest.mark.unit.mark)
    for item in items:
        if "gui_system" in item.nodeid:
            item.add_marker(pytest.mark.system)
        else:
            item.add_marker(pytest.mark.unit)
        if any(mark in allowed_markers for mark in item.own_markers):
            pass
        else:
            item.add_marker(pytest.mark.skip(reason="Test not selected"))
            skipped_tests.append(item.nodeid)
