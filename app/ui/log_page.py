"""Seite „Protokoll“ – zeigt die Log-Ausgabe der App."""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from ..paths import LOG_DIR


class _Bridge(QObject):
    message = Signal(str)


class QtLogHandler(logging.Handler):
    """Leitet Log-Einträge (aus beliebigen Threads) an die Oberfläche weiter."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self._bridge = _Bridge()
        self.message = self._bridge.message
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))
        self.buffer: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self.format(record)
        except Exception:
            return
        self.buffer = (self.buffer + [text])[-500:]
        self.message.emit(text)


class LogPage(QWidget):
    def __init__(self, handler: QtLogHandler) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        head = QHBoxLayout()
        title = QLabel("Protokoll")
        title.setProperty("h2", True)
        head.addWidget(title)
        head.addStretch(1)
        clear = QPushButton("Leeren")
        folder = QPushButton("Log-Ordner öffnen")
        folder.clicked.connect(lambda: os.startfile(LOG_DIR))
        head.addWidget(clear)
        head.addWidget(folder)
        root.addLayout(head)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(2000)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        root.addWidget(self.text, 1)
        clear.clicked.connect(self.text.clear)
        for line in handler.buffer:
            self.text.appendPlainText(line)
        handler.message.connect(self.text.appendPlainText)
