from PyQt6.QtTest import QTest

from rascal2.dialogs.startup_dialog import LoadDialog
from tests.system.gui_system_base import SHORT_DELAY, GuiSystemBase


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
