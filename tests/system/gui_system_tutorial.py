from pathlib import Path

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton

from rascal2.dialogs.startup_dialog import LoadDialog
from rascal2.widgets.project.lists import StandardLayerModelWidget
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
        ex_param_model = (
            self.main_window.project_widget.view_tabs["Experimental Parameters"].tables["scalefactors"].model)
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
        self.main_window.project_widget.edit_project_button.click()
        QApplication.processEvents()
        QTest.qWait(SHORT_DELAY)
        table_model = self.main_window.project_widget.edit_tabs["Parameters"].tables['parameters'].model
        add_param_button = self.main_window.project_widget.edit_tabs["Parameters"].tables["parameters"].add_button
        old_row_count = table_model.rowCount()
        add_param_button.click()
        assert table_model.rowCount() == old_row_count + 1
        table_model.setData(table_model.index(1, 1), 2)
        table_model.setData(table_model.index(1, 2), "Si02 Thickness")
        table_model.setData(table_model.index(1, 3), 0)
        table_model.setData(table_model.index(1, 4), 10)
        table_model.setData(table_model.index(1, 5), 25)

        add_param_button.click()
        table_model.setData(table_model.index(2, 1), 2)
        table_model.setData(table_model.index(2, 2), "Si02 Roughness")
        table_model.setData(table_model.index(2, 3), 0)
        table_model.setData(table_model.index(2, 4), 3)
        table_model.setData(table_model.index(2, 5), 7)

        add_param_button.click()
        table_model.setData(table_model.index(3, 1), 0)
        table_model.setData(table_model.index(3, 2), "Si02 SLD")
        table_model.setData(table_model.index(3, 3), 0.0000033)
        table_model.setData(table_model.index(3, 4), 0.00000341)
        table_model.setData(table_model.index(3, 5), 0.0000035)

        add_param_button.click()
        table_model.setData(table_model.index(4, 1), 2)
        table_model.setData(table_model.index(4, 2), "Si02 Hydration")
        table_model.setData(table_model.index(4, 3), 0)
        table_model.setData(table_model.index(4, 4), 20)
        table_model.setData(table_model.index(4, 5), 30)

        QTest.qWait(SHORT_DELAY)

        self.main_window.project_widget.project_tab.setCurrentIndex(2)
        self.main_window.project_widget.edit_tabs["Layers"].tables["layers"].add_button.click()
        layer_table_model = self.main_window.project_widget.edit_tabs["Layers"].tables['layers'].model
        layer_table_model.beginResetModel()

        layer_table_model.setData(layer_table_model.index(0, 1), "Si02")
        layer_table_model.setData(layer_table_model.index(0, 2), "Si02 Thickness")
        layer_table_model.setData(layer_table_model.index(0, 3), "Si02 SLD")
        layer_table_model.setData(layer_table_model.index(0, 4), "Si02 Roughness")
        layer_table_model.setData(layer_table_model.index(0, 5), "Si02 Hydration")
        layer_table_model.setData(layer_table_model.index(0, 6), "bulk out")

        QTest.qWait(SHORT_DELAY)
        self.main_window.project_widget.project_tab.setCurrentIndex(8)
        con_widget = self.main_window.project_widget.edit_tabs['Contrasts'].tables['contrasts']
        slm = con_widget.findChildren(StandardLayerModelWidget)[0]
        slm.add_button.click()

        QApplication.processEvents()
        self.main_window.setFocus()
        wait_until(lambda: slm.model.data(slm.model.index(0, 0)) == 'Si02', max_retry=1000)

        assert slm.model.rowCount() == 1
        self.main_window.project_widget.save_project_button.click()
        QApplication.processEvents()
        QTest.qWait(SHORT_DELAY)
        self.main_window.controls_widget.run_button.click()
        wait_until(
            lambda: "Finished RAT" in self.main_window.terminal_widget.text_area.toPlainText()
        )
        QTest.qWait(SHORT_DELAY)
        assert self.main_window.controls_widget.chi_squared.text() == '1.51665'
