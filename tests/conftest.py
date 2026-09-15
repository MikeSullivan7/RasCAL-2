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
    parser.addoption("--skip_system_tests", action="store_true", default=False, help="Skip GUI system tests")
    parser.addoption("--run_slow_tests", action="store_true", default=False, help="Run slow tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "system: GUI system tests")
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "slow: marks slow tests which only run on review")


allowed_markers = []
skipped_tests = []


def pytest_collection_modifyitems(config, items):
    allowed_markers.append(pytest.mark.unit.mark)
    if not config.getoption("--skip_system_tests"):
        allowed_markers.append(pytest.mark.system.mark)
    if config.getoption("--run_slow_tests"):
        allowed_markers.append(pytest.mark.slow.mark)
    for item in items:
        if "gui_system" in item.nodeid:
            item.add_marker(pytest.mark.system)
        if "slow" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        else:
            item.add_marker(pytest.mark.unit)
        for mark in item.own_markers:
            if "parametrize" in mark.name:
                continue
            if mark not in allowed_markers:
                item.add_marker(pytest.mark.skip(reason="Test not selected"))
                skipped_tests.append(item.nodeid)
                break
