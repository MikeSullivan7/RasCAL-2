from PyQt6 import QtCore, QtGui, QtWidgets

from rascal2.dialogs.startup_dialog import LoadDialog, LoadR1Dialog, NewProjectDialog
from rascal2.paths import path_for


class StartUpWidget(QtWidgets.QWidget):
    """The StartUp widget."""

    def __init__(self, parent):
        """Initialize widget.

        Parameters
        ----------
        parent: MainWindowView
                An instance of the MainWindowView
        """
        super().__init__(parent)

        self.create_banner_and_footer()
        self.create_buttons()
        self.create_labels()

        self.add_widgets_to_layout()

    def add_widgets_to_layout(self) -> None:
        """Add widgets to layout."""
        startup_layout = QtWidgets.QVBoxLayout()

        startup_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        startup_layout.setSpacing(50)

        # Add banner
        startup_layout.addStretch(1)
        startup_layout.addWidget(self.banner_label)

        # Add buttons and labels
        for widget in ["button", "label"]:
            layout = QtWidgets.QHBoxLayout()
            for name in ["new_project_", "import_project_", "import_r1_"]:
                layout.addWidget(getattr(self, name + widget))
            startup_layout.addLayout(layout)

        # Add footer
        startup_layout.addWidget(self.footer_label)
        startup_layout.addStretch(1)

        self.setLayout(startup_layout)

    def create_banner_and_footer(self) -> None:
        """Create banner and footer."""
        self.banner_label = QtWidgets.QLabel()
        self.banner_label.setPixmap(QtGui.QPixmap(path_for("banner-light.png")))
        self.banner_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.footer_label = QtWidgets.QLabel()
        self.footer_label.setPixmap(QtGui.QPixmap(path_for("footer-light.png")))
        self.footer_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    def create_buttons(self) -> None:
        """Create buttons."""
        self.new_project_button = QtWidgets.QToolButton(objectName="NewProjectButton")
        self.new_project_button.clicked.connect(lambda: self.parent().show_project_dialog(NewProjectDialog))

        self.import_project_button = QtWidgets.QToolButton(objectName="ImportProjectButton")
        self.import_project_button.clicked.connect(lambda: self.parent().show_project_dialog(LoadDialog))

        self.import_r1_button = QtWidgets.QToolButton(objectName="ImportR1Button")
        self.import_r1_button.clicked.connect(lambda: self.parent().show_project_dialog(LoadR1Dialog))

    def create_labels(self) -> None:
        """Create labels."""
        self.new_project_label = QtWidgets.QLabel("New\nProject")
        self.new_project_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.import_project_label = QtWidgets.QLabel("Import Existing\nProject")
        self.import_project_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.import_r1_label = QtWidgets.QLabel("Import RasCAL-1\nProject")
        self.import_r1_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.Type.PaletteChange:
            scheme = QtWidgets.QApplication.styleHints().colorScheme()
            if scheme == QtCore.Qt.ColorScheme.Dark:
                self.banner_label.setPixmap(QtGui.QPixmap(path_for("banner-dark.png")))
                self.footer_label.setPixmap(QtGui.QPixmap(path_for("footer-dark.png")))
            else:
                self.banner_label.setPixmap(QtGui.QPixmap(path_for("banner-light.png")))
                self.footer_label.setPixmap(QtGui.QPixmap(path_for("footer-light.png")))

        super().changeEvent(event)
