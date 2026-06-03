import re
from contextlib import suppress

from PyQt6 import QtCore, QtGui, QtWidgets

from rascal2.paths import IMAGES_PATH, STATIC_PATH, path_for


def set_stylesheet(app):
    """Set the stylesheet of the app according to the given style.css file if available."""
    with suppress(FileNotFoundError), open(STATIC_PATH / "style.css") as stylesheet:
        palette = app.palette()
        replacements = {
            "@Path": IMAGES_PATH.as_posix(),
            "@Window": palette.window().color().name(),
            "@Highlight": palette.highlight().color().name(),
            "@Midlight": palette.midlight().color().name(),
            "@Text": palette.text().color().name(),
        }
        style = re.sub("|".join(replacements), lambda x: replacements[x.group(0)], stylesheet.read())
        app.setStyleSheet(style)


class ThemeManager(QtCore.QObject):
    """Class to manage the Theme of the UI."""

    def __init__(self):
        super().__init__()
        scheme = QtWidgets.QApplication.styleHints().colorScheme()
        self.cur_style = "light" if scheme == QtCore.Qt.ColorScheme.Light else "dark"

    def eventFilter(self, obj, event):
        """Catch close event for overlay widget."""
        if isinstance(obj, QtWidgets.QApplication) and event.type() == QtCore.QEvent.Type.ApplicationPaletteChange:
            scheme = QtWidgets.QApplication.styleHints().colorScheme()
            style = "light" if scheme == QtCore.Qt.ColorScheme.Light else "dark"
            if style != self.cur_style:
                set_stylesheet(obj)
                self.cur_style = style
                return True
        return False


THEMES = ThemeManager()


class IconEngine(QtGui.QIconEngine):
    """Create the icons for the application."""

    def __init__(self, filename):
        super().__init__()
        self.name = re.split(r"-dark.png|-light.png", filename)[0]
        self.update_icon()

    def update_icon(self):
        """Update the Icon."""
        scheme = QtWidgets.QApplication.styleHints().colorScheme()
        style = "light" if scheme == QtCore.Qt.ColorScheme.Light else "dark"

        filename = f"{self.name}-light.png" if style == "light" else f"{self.name}-dark.png"
        path = path_for(filename)
        self.icon = QtGui.QIcon(path)

    def pixmap(self, size, mode, state):
        """Create the pixmap.

        :param size: size
        :type size: QSize
        :param mode: mode
        :type mode: QIcon.Mode
        :param state: state
        :type state: QIcon.State
        """
        self.update_icon()
        return self.icon.pixmap(size, mode, state)

    def paint(self, painter, rect, mode, state):
        """Paint the icon.

        :param painter: painter
        :type painter: QPainter
        :param rect: rect
        :type rect: QRect
        :param mode: mode
        :type mode: QIcon.Mode
        :param state: state
        :type state: QIcon.State
        """
        self.update_icon()
        return self.icon.pixmap.paint(painter, rect, mode, state)
