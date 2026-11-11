"""Hell/Dunkel und Stylesheet."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

STYLE = """
QLabel[h2="true"] { font-size: 17px; font-weight: 600; }
QLabel[h3="true"] { font-size: 14px; font-weight: 600; margin-top: 10px; }
QLabel[hint="true"] { color: palette(placeholder-text); }
QGroupBox { font-weight: 600; border: 1px solid palette(mid); border-radius: 10px;
            margin-top: 14px; padding: 12px 10px 10px 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QListWidget#nav { border: none; background: transparent; font-size: 14px; outline: 0; }
QListWidget#nav::item { padding: 10px 14px; border-radius: 8px; margin: 2px 6px; }
QListWidget#nav::item:selected { background: #6c5ce7; color: white; }
QPushButton[deckButton="true"] { border: 1px solid palette(mid); border-radius: 10px; padding: 6px;
                                 background: palette(base); text-align: center; }
QPushButton[deckButton="true"][assigned="true"] { border: 1px solid #6c5ce7; }
QPushButton[deckButton="true"]:hover { background: palette(alternate-base); }
QPushButton[deckButton="true"][active="true"] { background: #6c5ce7; color: white; }
QPushButton[primary="true"] { background: #6c5ce7; color: white; border-radius: 6px; padding: 6px 14px; }
"""


def apply_theme(mode: str) -> None:
    app = QApplication.instance()
    hints = app.styleHints()
    scheme = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(mode, Qt.ColorScheme.Unknown)
    try:
        if scheme == Qt.ColorScheme.Unknown:
            hints.unsetColorScheme()
        else:
            hints.setColorScheme(scheme)
    except AttributeError:
        pass


def setup_style(app: QApplication, mode: str) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    apply_theme(mode)
