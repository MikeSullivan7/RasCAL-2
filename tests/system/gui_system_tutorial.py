from pathlib import Path

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton

from rascal2.dialogs.startup_dialog import LoadDialog
from tests.system.gui_system_base import SHORT_DELAY, GuiSystemBase, wait_until


class TestGuiSystemLoading(GuiSystemBase):
    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def test_loading_si_d2o_interface(self):
        QTest.qWait(SHORT_DELAY)
        self.main_window.startup_dlg.import_project_button.click()
        load_dialog = self.main_window.findChild(LoadDialog)
        load_dialog.tabs.setCurrentIndex(2)
        filename = str(Path(__file__, "../../data/tutorial_system_files/Si_D2O_interface/").resolve())
        load_dialog.project_folder.setText(filename)
        buttons = load_dialog.tabs.findChildren(QPushButton)
        load_button = [button for button in buttons if button.text() == "Load"][0]
        load_button.click()
        wait_until(lambda: self.main_window.controls_widget.chi_squared.text() != "")
        assert self.main_window.controls_widget.chi_squared.text() == "244.588"
        assert self.main_window.controls_widget.procedure_dropdown.currentText() == "simplex"
        QTest.qWait(SHORT_DELAY)
        model = self.main_window.project_widget.view_tabs["Parameters"].tables["parameters"].model
        assert model.classlist.data[0].name == "Substrate Roughness"
        assert model.classlist.data[0].value == 6.811291229641589
        assert model.classlist.data[0].min == 1.0
        assert model.classlist.data[0].max == 20.0
        assert model.classlist.data[0].fit is True
