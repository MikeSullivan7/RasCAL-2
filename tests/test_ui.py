import sys

import pytest

from rascal2.ui.view import MainWindowView


@pytest.fixture
def make_main_window(request):
    def make():
        no_exceptions = True

        def exception_hook(exc_type, exc_value, exc_traceback):
            nonlocal no_exceptions
            no_exceptions = False
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

        sys.excepthook = exception_hook

        window = MainWindowView()

        def cleanup():
            nonlocal no_exceptions
            if not no_exceptions:
                raise Exception("An exception occurred in a PyQt slot")
            sys.excepthook = sys.__excepthook__

        request.addfinalizer(cleanup)
        return window

    return make


def test_integration(qt_application, make_main_window):
    _ = qt_application
    window = make_main_window()
    window.show()
    print("test_integration 1")

    window.presenter.create_project("project", ".")
    print("test_integration 2")
    names = [win.windowTitle() for win in window.mdi.subWindowList()]
    print("test_integration 3")
    # QMDIArea is first in last out hence the reversed list
    assert names == ["Fitting Controls", "Terminal", "Project", "Plots"]
    print("test_integration 4")

    # Work through the different sections of the UI

    window.close()
    print("test_integration 5")
