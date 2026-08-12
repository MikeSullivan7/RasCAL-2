from tests.system.gui_system_base import GuiSystemBase


class TestGuiSystemLoading(GuiSystemBase):
    leak_count_limit = 2

    def setUp(self) -> None:
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()

    def test_load(self):
        pass
