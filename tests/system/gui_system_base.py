import logging
import sys
import unittest
from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from rascal2.config import setup_logging
from rascal2.ui.view import MainWindowView

SHOW_DELAY = 10  # Can be increased to watch tests
SHORT_DELAY = 100


def wait_until(
    test_func: Callable[[], bool], delay=0.1, max_retry=100, message: str = "wait_until reached max retries"
):
    """Repeat test_func every delay seconds until it becomes true. Raises RuntimeError if max_retry is reached."""
    for _ in range(max_retry):
        if test_func():
            return True
        QTest.qWait(int(delay * 1000))
    raise RuntimeError(message)


class GuiSystemBase(unittest.TestCase):
    app: QApplication = QApplication.instance()

    def setUp(self) -> None:
        setup_logging()
        self.no_exceptions = True

        sys.excepthook = self.exception_hook
        self.main_window = MainWindowView()
        self.main_window.show()
        QTest.qWait(SHORT_DELAY)

    def tearDown(self) -> None:
        if not self.no_exceptions:
            raise Exception("An exception occurred in a PyQt slot")
        sys.excepthook = sys.__excepthook__
        logger = logging.getLogger("rascal2")
        logger.handlers.clear()
        if not self.main_window.presenter.runner.exit_event.is_set():
            self.main_window.presenter.runner.exit_event.set()
        if not self.main_window.presenter.runner.go_event.is_set():
            self.main_window.presenter.runner.go_event.set()
        QTimer.singleShot(SHORT_DELAY, lambda: self._click_messagebox())
        self.main_window.close()
        wait_until(
            lambda: not self.main_window.isVisible(),
            delay=0.05,
            max_retry=200,
            message="Main window did not close within 10 seconds",
        )
        del self.main_window

    def exception_hook(self, exc_type, exc_value, exc_traceback):
        self.no_exceptions = False
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    @classmethod
    def _click_messagebox(cls):
        """Needs to be queued with QTimer.singleShot before triggering the message box."""
        no_buttons_found = True
        button_texts = []
        for widget in cls.app.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                for button in widget.buttons():
                    if widget.buttonRole(button) == widget.ButtonRole.DestructiveRole:
                        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                        no_buttons_found = False
                    button_texts = [button.text() for button in widget.buttons()]
                if no_buttons_found:
                    raise ValueError(
                        f"Could not find buttons in {button_texts}'.\n"
                        f"Message box: {widget.windowTitle()} {widget.text()}"
                    )
