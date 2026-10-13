from pathlib import Path
from unittest import mock

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QComboBox, QLineEdit

from rascal2.dialogs.custom_file_editor import CustomFileEditorDialog
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


class TestGuiTutorial(GuiSystemBase):
    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def switch_to_tab(self, tab_name: str) -> None:
        project_tab = self.main_window.project_widget.project_tab
        tab_names = [project_tab.tabText(ind) for ind in range(0, project_tab.count())]
        [project_tab.setCurrentIndex(ind) for ind in range(0, project_tab.count()) if tab_names[ind] == tab_name]

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
            self.main_window.project_widget.view_tabs["Experimental Parameters"].tables["scalefactors"].model
        )
        assert param_model.classlist.data[0].value == 6.811291229641589
        assert ex_param_model.classlist.data[0].value == 0.1
        self.main_window.controls_widget.run_button.click()
        wait_until(lambda: "Finished RAT" in self.main_window.terminal_widget.text_area.toPlainText())
        QTest.qWait(SHORT_DELAY)
        param_model = self.main_window.project_widget.view_tabs["Parameters"].tables["parameters"].model
        ex_param_model = (
            self.main_window.project_widget.view_tabs["Experimental Parameters"].tables["scalefactors"].model
        )
        assert self.main_window.controls_widget.chi_squared.text() == "1.46999"
        assert round(param_model.classlist.data[0].value, 4) == 6.6938
        assert round(ex_param_model.classlist.data[0].value, 3) == 1.000

    def test_adding_parameters(self):
        load_tutorial_file(self.main_window, "../../data/tutorial_system_files/Si_D2O_interface/")
        wait_until(lambda: self.main_window.controls_widget.chi_squared.text() != "")
        self.main_window.project_widget.edit_project_button.click()
        QApplication.processEvents()
        QTest.qWait(SHORT_DELAY)
        table_model = self.main_window.project_widget.edit_tabs["Parameters"].tables["parameters"].model
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
        layer_table_model = self.main_window.project_widget.edit_tabs["Layers"].tables["layers"].model
        layer_table_model.beginResetModel()

        layer_table_model.setData(layer_table_model.index(0, 1), "Si02")
        layer_table_model.setData(layer_table_model.index(0, 2), "Si02 Thickness")
        layer_table_model.setData(layer_table_model.index(0, 3), "Si02 SLD")
        layer_table_model.setData(layer_table_model.index(0, 4), "Si02 Roughness")
        layer_table_model.setData(layer_table_model.index(0, 5), "Si02 Hydration")
        layer_table_model.setData(layer_table_model.index(0, 6), "bulk out")

        QTest.qWait(SHORT_DELAY)
        self.main_window.project_widget.project_tab.setCurrentIndex(8)
        con_widget = self.main_window.project_widget.edit_tabs["Contrasts"].tables["contrasts"]
        slm = con_widget.findChildren(StandardLayerModelWidget)[0]
        slm.add_button.click()

        QApplication.processEvents()
        self.main_window.setFocus()
        wait_until(lambda: slm.model.data(slm.model.index(0, 0)) == "Si02", max_retry=1000)

        assert slm.model.rowCount() == 1
        self.main_window.project_widget.save_project_button.click()
        QApplication.processEvents()
        QTest.qWait(SHORT_DELAY)
        self.main_window.controls_widget.run_button.click()
        wait_until(lambda: "Finished RAT" in self.main_window.terminal_widget.text_area.toPlainText())
        QTest.qWait(SHORT_DELAY)
        assert self.main_window.controls_widget.chi_squared.text() == "1.51665"

    def test_custom_model_fitting(self):
        load_tutorial_file(self.main_window, "../../data/tutorial_system_files/Part_2_Custom_Model_Fitting/")
        wait_until(lambda: self.main_window.controls_widget.chi_squared.text() == "1.5161")
        self.main_window.project_widget.edit_project_button.click()
        table = self.main_window.project_widget.edit_tabs["Parameters"].tables["parameters"]
        table.table.indexWidget(table.model.index(3, 0)).click()
        assert table.model.rowCount() == 4
        project_tab = self.main_window.project_widget.project_tab
        self.main_window.project_widget.model_combobox.setCurrentText("custom layers")
        
        self.switch_to_tab("Custom Files")
        assert project_tab.tabText(project_tab.currentIndex()) == "Custom Files"
        self.main_window.project_widget.edit_tabs["Custom Files"].tables["custom_files"].add_button.click()
        custom_file_widget = self.main_window.project_widget.edit_tabs["Custom Files"].tables["custom_files"]
        assert custom_file_widget.model.rowCount() == 1
        QTest.qWait(SHORT_DELAY)
        filename = str(
            Path(__file__, "../../data/tutorial_system_files/Part_2_Custom_Model_Fitting/custom_model.py").resolve()
        )
        custom_file_widget.model.setData(custom_file_widget.model.index(0, 3), filename)
        custom_file_widget.model.setData(custom_file_widget.model.index(0, 2), "Custom_model")
        QApplication.processEvents()

        custom_file_widget.table.indexWidget(custom_file_widget.model.index(0, 1)).click()
        QTest.qWait(SHORT_DELAY)
        editor_buttons = self.main_window.findChild(CustomFileEditorDialog).findChildren(QPushButton)
        editor_buttons[0].click()
        editor_buttons[1].click()

        self.switch_to_tab("Contrasts")
        con_widget = self.main_window.project_widget.edit_tabs["Contrasts"].tables["contrasts"]
        custom_model_name = custom_file_widget.model.data(custom_file_widget.model.index(0, 2))
        slm = list(filter(lambda x: x.itemText(0) == custom_model_name, con_widget.findChildren(QComboBox)))[0]
        slm.setCurrentIndex(0)
        self.main_window.project_widget.save_project_button.click()
        self.main_window.controls_widget.run_button.click()
        wait_until(lambda: "Finished RAT" in self.main_window.terminal_widget.text_area.toPlainText())
        QTest.qWait(SHORT_DELAY)
        assert self.main_window.controls_widget.chi_squared.text() == "1.50127"

        self.main_window.project_widget.edit_project_button.click()

        self.switch_to_tab("Experimental Parameters")

        bulk_out_widget = self.main_window.project_widget.edit_tabs["Experimental Parameters"].tables["bulk_out"]
        bulk_out_widget.add_button.click()
        bulk_out_widget.model.setData(bulk_out_widget.model.index(1, 2), 2)
        bulk_out_widget.model.setData(bulk_out_widget.model.index(1, 2), "SLD H2O")
        bulk_out_widget.model.setData(bulk_out_widget.model.index(1, 3), -0.6e-6)
        bulk_out_widget.model.setData(bulk_out_widget.model.index(1, 4), -0.56e-6)
        bulk_out_widget.model.setData(bulk_out_widget.model.index(1, 5), -0.4e-6)

        QTest.qWait(SHORT_DELAY)

        self.switch_to_tab("Data")

        data_filename = str(
            Path(__file__, "../../data/tutorial_system_files/Part_2_Custom_Model_Fitting/Si_H2O.dat").resolve()
        )
        self.main_window.project_widget.edit_tabs["Data"].tables["data"].file_dialog = mock.Mock()
        self.main_window.project_widget.edit_tabs["Data"].tables["data"].file_dialog.getOpenFileNames.return_value = [
            [data_filename]
        ]
        self.main_window.project_widget.edit_tabs["Data"].tables["data"].add_button.click()
        QTest.qWait(SHORT_DELAY)

        self.switch_to_tab("Contrasts")
        con_widget.add_button.click()
        con_widget.findChildren(QLineEdit)[1].setText("Si H2O")

        self.switch_to_tab("Backgrounds")
        back_param_widget = self.main_window.project_widget.edit_tabs["Backgrounds"].tables["background_parameters"]
        back_param_widget.add_button.click()
        back_param_widget.model.setData(back_param_widget.model.index(1, 1), 2)
        back_param_widget.model.setData(back_param_widget.model.index(1, 2), "Background Param 2")
        back_param_widget.model.setData(back_param_widget.model.index(1, 3), 1e-07)
        back_param_widget.model.setData(back_param_widget.model.index(1, 4), 5e-06)
        back_param_widget.model.setData(back_param_widget.model.index(1, 5), 1e-05)
        back_widget = self.main_window.project_widget.edit_tabs["Backgrounds"].tables["backgrounds"]
        back_widget.add_button.click()
        back_widget.model.setData(back_widget.model.index(1, 1), "Background 2")
        back_widget.model.setData(back_widget.model.index(1, 3), "Background Param 2")

        self.switch_to_tab("Contrasts")
        for key, value in con_widget.model.classlist[0].__dict__.items():
            match key:
                case "data" | "name":
                    con_widget.model.set_data(1, key, "Si_H2O")
                case "bulk_out":
                    con_widget.model.set_data(1, key, "SLD H2O")
                case "background":
                    con_widget.model.set_data(1, key, "Background 2")
                case _:
                    con_widget.model.set_data(1, key, value)
        self.main_window.project_widget.save_project_button.click()
        QTest.qWait(SHORT_DELAY)
        for _ in range(0, 3):
            self.main_window.controls_widget.run_button.click()
            wait_until(
                lambda: "Finished RAT" in self.main_window.terminal_widget.text_area.toPlainText(), max_retry=200
            )
            print(f"{self.main_window.controls_widget.chi_squared.text()=}")
            if self.main_window.controls_widget.chi_squared.text() == "2.63417":
                break
        assert self.main_window.controls_widget.chi_squared.text() == "2.63417"
