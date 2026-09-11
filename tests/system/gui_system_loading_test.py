from pathlib import Path

from parameterized import parameterized
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rascal2.dialogs.startup_dialog import LoadDialog
from tests.system.gui_system_base import SHORT_DELAY, GuiSystemBase, wait_until

EXAMPLES_PATH = Path(__file__, "../../../examples").resolve().as_posix()


class TestGuiSystemLoading(GuiSystemBase):
    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def test_load(self):
        QTest.qWait(SHORT_DELAY)
        self.main_window.startup_dlg.import_project_button.click()
        load_dialog = self.main_window.findChild(LoadDialog)
        load_dialog.tabs.setCurrentIndex(2)
        load_dialog.example_list_widget.itemClicked.emit(load_dialog.example_list_widget.item(0))
        QTest.qWait(SHORT_DELAY)
        assert self.main_window.presenter.model.project.name == "DSPC Standard Layers"

    @parameterized.expand(
        [
            ("calculate", 142.346, 1000),
            ("simplex", 13.1816, 1000),
            ("de", 10.4746, 1000),
            ("ns", [9, 11], 4000),
            ("dream", 9.67234, 1000),
        ]
    )
    def test_run(self, procedure_name, expected_chi, test_duration):
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
        wait_until(
            lambda: "Finished RAT" in self.main_window.terminal_widget.text_area.toPlainText(), max_retry=test_duration
        )
        QTest.qWait(SHORT_DELAY)
        if isinstance(expected_chi, list):
            assert expected_chi[0] <= float(self.main_window.controls_widget.chi_squared.text()) <= expected_chi[1]
        else:
            assert self.main_window.controls_widget.chi_squared.text() == str(expected_chi)
        assert self.main_window.presenter.runner.error is None
