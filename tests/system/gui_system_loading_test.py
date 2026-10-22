import random
from pathlib import Path

from parameterized import parameterized
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rascal2.dialogs.startup_dialog import LoadDialog
from tests.system.gui_system_base import SHORT_DELAY, GuiSystemBase, wait_until

EXAMPLES_PATH = Path(__file__, "../../../examples").resolve().as_posix()


class TestGuiSystemLoading(GuiSystemBase):
    def setUp(self) -> None:
        random.seed(20)
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def watch_output(self, test_duration=100) -> None:
        while "Finished RAT" not in (
            most_recent_line := self.main_window.terminal_widget.text_area.toPlainText().split("\n")[-1]
        ):
            wait_until(
                lambda: self.main_window.terminal_widget.text_area.toPlainText().split("\n")[-1] != most_recent_line,
                max_retry=test_duration
            )

    def test_load(self):
        QTest.qWait(SHORT_DELAY)
        self.main_window.startup_dlg.import_project_button.click()
        load_dialog = self.main_window.findChild(LoadDialog)
        load_dialog.tabs.setCurrentIndex(2)
        load_dialog.example_list_widget.itemClicked.emit(load_dialog.example_list_widget.item(0))
        wait_until(lambda: self.main_window.controls_widget.chi_squared.text() != "")
        assert self.main_window.presenter.model.project.name == "DSPC Standard Layers"

    @parameterized.expand(
        [
            ("calculate", 142.346),
            ("simplex", 13.1816),
            ("de", 10.4746),
        ]
    )
    def test_run(self, procedure_name, expected_chi):
        QTest.qWait(SHORT_DELAY)
        self.main_window.startup_dlg.import_project_button.click()
        load_dialog = self.main_window.findChild(LoadDialog)
        load_dialog.tabs.setCurrentIndex(2)
        load_dialog.example_list_widget.itemClicked.emit(load_dialog.example_list_widget.item(0))
        wait_until(lambda: self.main_window.controls_widget.chi_squared.text() != "")
        self.main_window.controls_widget.update_chi_squared("")
        self.main_window.controls_widget.procedure_dropdown.setCurrentText(procedure_name)
        QApplication.processEvents()
        self.main_window.controls_widget.run_button.click()
        self.watch_output()
        QTest.qWait(SHORT_DELAY)
        assert self.main_window.controls_widget.chi_squared.text() == str(expected_chi)
        assert self.main_window.presenter.runner.error is None

    @parameterized.expand(
        [
            ("dream", 9.67234, 2000),
        ]
    )
    def test_run_slow(self, procedure_name, expected_chi, test_duration):
        self.main_window.startup_dlg.import_project_button.click()
        load_dialog = self.main_window.findChild(LoadDialog)
        load_dialog.tabs.setCurrentIndex(2)
        load_dialog.example_list_widget.itemClicked.emit(load_dialog.example_list_widget.item(0))
        wait_until(lambda: self.main_window.controls_widget.chi_squared.text() != "")
        self.main_window.controls_widget.update_chi_squared("")
        self.main_window.controls_widget.procedure_dropdown.setCurrentText(procedure_name)
        QApplication.processEvents()
        self.main_window.controls_widget.run_button.click()
        self.watch_output(test_duration)
        QTest.qWait(SHORT_DELAY)
        assert self.main_window.controls_widget.chi_squared.text() == str(expected_chi)
        assert self.main_window.presenter.runner.error is None
