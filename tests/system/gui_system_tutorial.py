from pathlib import Path

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton, QMainWindow, QApplication

from rascal2.dialogs.startup_dialog import LoadDialog
from tests.system.gui_system_base import SHORT_DELAY, GuiSystemBase, wait_until


def load_tutorial_file(main_window: QMainWindow, file_path: Path | str):
    main_window.startup_dlg.import_project_button.click()
    load_dialog = main_window.findChild(LoadDialog)
    load_dialog.tabs.setCurrentIndex(2)
    filename = str(Path(__file__, file_path).resolve())
    load_dialog.project_folder.setText(filename)
    buttons = load_dialog.tabs.findChildren(QPushButton)
    load_button = [button for button in buttons if button.text() == "Load"][0]
    load_button.click()


class TestGuiSystemLoading(GuiSystemBase):
    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def test_loading_si_d2o_interface(self):
        load_tutorial_file(self.main_window, "../../data/tutorial_system_files/Si_D2O_interface/")
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

    def test_fitting_simplex(self):
        load_tutorial_file(self.main_window, "../../data/tutorial_system_files/Si_D2O_interface/")
        wait_until(lambda: self.main_window.controls_widget.chi_squared.text() != "")
        param_model = self.main_window.project_widget.view_tabs["Parameters"].tables["parameters"].model
        ex_param_model = self.main_window.project_widget.view_tabs["Experimental Parameters"].tables["scalefactors"].model
        assert param_model.classlist.data[0].value == 6.811291229641589
        assert ex_param_model.classlist.data[0].value == 0.1
        self.main_window.controls_widget.run_button.click()
        wait_until(
            lambda: "Finished RAT" in self.main_window.terminal_widget.text_area.toPlainText()
        )
        QTest.qWait(SHORT_DELAY)
        param_model = self.main_window.project_widget.view_tabs["Parameters"].tables["parameters"].model
        ex_param_model = self.main_window.project_widget.view_tabs["Experimental Parameters"].tables[
            "scalefactors"].model
        assert self.main_window.controls_widget.chi_squared.text() == '1.46999'
        assert round(param_model.classlist.data[0].value, 4) == 6.6938
        assert round(ex_param_model.classlist.data[0].value, 3) == 1.000

    def test_adding_parameters(self):
        load_tutorial_file(self.main_window, "../../data/tutorial_system_files/Si_D2O_interface/")
        wait_until(lambda: self.main_window.controls_widget.chi_squared.text() != "")
        QTest.qWait(SHORT_DELAY * 100)
        self.main_window.project_widget.edit_project_button.click()
        print(self.main_window.project_widget.view_tabs["Parameters"].tables["parameters"])
        QApplication.processEvents()
        QTest.qWait(SHORT_DELAY)
        self.main_window.project_widget.view_tabs["Parameters"].beginResetModel()
        self.main_window.project_widget.view_tabs["Parameters"].tables["parameters"].add_button.click()
        self.main_window.project_widget.view_tabs["Parameters"].tables["parameters"].add_button.click()

        QApplication.processEvents()
        QTest.qWait(SHORT_DELAY*100)
