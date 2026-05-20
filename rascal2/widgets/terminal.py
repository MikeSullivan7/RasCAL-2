"""Widget for terminal display."""

import logging

from PyQt6 import QtGui, QtWidgets

from rascal2 import RASCAL2_VERSION


class CustomStreamHandler(logging.StreamHandler):
    """Log stream handler to ensure messages are formatted properly in terminal."""

    def emit(self, record):
        try:
            msg = self.format(record) + self.terminator
            if record.levelno >= logging.ERROR:
                self.stream.write_error(msg)
            else:
                self.stream.write(msg)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


class TerminalWidget(QtWidgets.QWidget):
    """Widget for displaying program output."""

    def __init__(self):
        super().__init__()

        self.text_area = QtWidgets.QPlainTextEdit()
        self.text_area.setReadOnly(True)
        font = QtGui.QFont()
        font.setFamily("Courier")
        font.setStyleHint(font.StyleHint.Monospace)
        self.text_area.setFont(font)
        self.text_area.setLineWrapMode(self.text_area.LineWrapMode.NoWrap)

        widget_layout = QtWidgets.QVBoxLayout()

        widget_layout.addWidget(self.text_area)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximumHeight(15)
        self.progress_bar.setMinimumHeight(10)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setVisible(False)
        widget_layout.addWidget(self.progress_bar)

        widget_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(widget_layout)
        self.add_stream_handler()

    def add_stream_handler(self):
        """Add terminal as a stream for the log handler."""
        logger = logging.getLogger()
        log_term_handler = CustomStreamHandler(stream=self)
        term_formatting = logging.Formatter("%(levelname)s - %(message)s")
        log_term_handler.setFormatter(term_formatting)
        logger.addHandler(log_term_handler)

    def write(self, text: str):
        """Append plain text to the terminal.

        Parameters
        ----------
        text : str
            The text to append.

        """
        self.text_area.appendPlainText(text.rstrip())

    def write_html(self, text: str):
        """Append HTML text to the terminal.

        Parameters
        ----------
        text : str
            The HTML to append.

        """
        self.text_area.appendHtml(text.rstrip())

    def write_error(self, text: str):
        """Append error text to the terminal and alert the user.

        Parameters
        ----------
        text : str
            The text to append.

        """
        self.write_html(f'<div style="color: crimson;white-space: pre-line;"><b>{text}</b></div>')

    def clear(self):
        """Clear the text in the terminal."""
        self.write_html('<div style="white-space: pre-line;"><b>" "</b></div>')
        self.text_area.moveCursor(QtGui.QTextCursor.MoveOperation.Start, QtGui.QTextCursor.MoveMode.MoveAnchor)
        self.text_area.setPlainText("")
        self.update()

    def write_startup(self):
        """Write the RasCAL-2 startup information to the terminal."""
        self.write(
            """
 ███████████                       █████████    █████████   █████
░░███░░░░░███                     ███░░░░░███  ███░░░░░███ ░░███
 ░███    ░███   ██████    █████  ███     ░░░  ░███    ░███  ░███
 ░██████████   ░░░░░███  ███░░  ░███          ░███████████  ░███
 ░███░░░░░███   ███████ ░░█████ ░███          ░███░░░░░███  ░███
 ░███    ░███  ███░░███  ░░░░███░░███     ███ ░███    ░███  ░███      █
 █████   █████░░████████ ██████  ░░█████████  █████   █████ ███████████
░░░░░   ░░░░░  ░░░░░░░░ ░░░░░░    ░░░░░░░░░  ░░░░░   ░░░░░ ░░░░░░░░░░░
"""
        )
        self.write_html(f"\n<b>RasCAL-2:</b> software for neutron reflectivity calculations <b>v{RASCAL2_VERSION}</b>")

        # set text area to be scrolled to the left at start
        self.text_area.moveCursor(QtGui.QTextCursor.MoveOperation.StartOfLine, QtGui.QTextCursor.MoveMode.MoveAnchor)

    def update_progress(self, event):
        """Update the progress bar from event data.

        Parameters
        ----------
        event : ProgressEventData
            The data for the current event.

        """
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(int(event.percent * 100))

    def flush(self):
        """Make TerminalWidget an IO stream."""
