from tests.system.gui_system_base import GuiSystemBase


class TestGuiSystemMainWindow(GuiSystemBase):
    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def test_main_window(self):
        self.main_window.presenter.create_project("project", ".")
        names = [win.windowTitle() for win in self.main_window.mdi.subWindowList()]
        assert names == ["Fitting Controls", "Terminal", "Project", "Plots"]
