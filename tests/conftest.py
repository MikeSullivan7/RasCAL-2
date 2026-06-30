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


@pytest.fixture(autouse=True)
@patch("rascal2.core.runner.cpu_count")
def fix_cpu_count(cpu_count):
    cpu_count.return_value = 1
    yield


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
    for target in ["rascal2.ui.view.get_global_settings", "rascal2.settings.get_global_settings"]:
        setting_patch.append(patch(target, return_value=GLOBAL_SETTING))
        setting_patch[-1].start()

    def teardown_mock_setting():
        global GLOBAL_SETTING
        GLOBAL_SETTING = None
        tmp_dir.cleanup()
        for target in setting_patch:
            target.stop()

    request.addfinalizer(teardown_mock_setting)
