import os
import unittest
from collections.abc import Callable

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

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
    app: QApplication

    def setUp(self) -> None:
        os.environ["START_PROCESSES"] = "False"
        self.main_window = MainWindowView()
        self.main_window.show()
        QTest.qWait(SHORT_DELAY)

    def tearDown(self) -> None:
        self.main_window.close()
        wait_until(
            lambda: not self.main_window.isVisible(),
            delay=0.05,
            max_retry=60,
            message="Main window did not close within 3 seconds",
        )
        del self.main_window
