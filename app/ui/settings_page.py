"""Seite „Einstellungen“."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, autostart
from ..device.serial_worker import available_ports
from ..paths import APP_DIR
from .theme import apply_theme

BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400]
LANGUAGES = [("de", "Deutsch (TT.MM)"), ("en", "English (DD/MM)"), ("it", "Italiano (DD/MM)"),
             ("es", "Español (DD/MM)"), ("fr", "Français (DD/MM)"), ("zh", "中文 (MM-DD)"), ("ja", "日本語 (MM/DD)")]
THEMES = [("system", "Wie Windows"), ("light", "Hell"), ("dark", "Dunkel")]


class SettingsPage(QWidget):
    def __init__(self, store, serial_worker) -> None:
        super().__init__()
        self.store = store
        self.serial = serial_worker

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)
        title = QLabel("Einstellungen")
        title.setProperty("h2", True)
        root.addWidget(title)

        # ---------------------------------------------------- Verbindung
        box = QGroupBox("Verbindung zum Deck")
        form = QFormLayout(box)
        row = QHBoxLayout()
        self.port = QComboBox()
        self.port.setMinimumWidth(300)
        self.port.activated.connect(self._save_serial)
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self._load_ports)
        row.addWidget(self.port, 1)
        row.addWidget(refresh)
        form.addRow("COM-Port", row)
        self.baud = QComboBox()
        for b in BAUD_RATES:
            self.baud.addItem(str(b), b)
        self.baud.setCurrentIndex(max(0, self.baud.findData(int(store.get("serial", "baud_rate", default=115200)))))
        self.baud.activated.connect(self._save_serial)
        form.addRow("Baudrate", self.baud)
        self.lang = QComboBox()
        for code, label in LANGUAGES:
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(store.get("language", default="de"))))
        self.lang.activated.connect(lambda: store.set("language", value=self.lang.currentData()))
        form.addRow("Datumsformat am Display", self.lang)
        root.addWidget(box)

        # ---------------------------------------------------- Verhalten
        box = QGroupBox("Programm")
        lay = QVBoxLayout(box)
        self.tray = QCheckBox("Beim Schließen in den Infobereich (Tray) minimieren")
        self.tray.setChecked(bool(store.get("app", "minimize_to_tray", default=True)))
        self.tray.toggled.connect(lambda v: store.set("app", "minimize_to_tray", value=v))
        self.autostart = QCheckBox("Mit Windows starten")
        self.autostart.setChecked(autostart.is_enabled())
        self.autostart.toggled.connect(self._set_autostart)
        self.minimized = QCheckBox("Minimiert starten (nur Tray-Symbol)")
        self.minimized.setChecked(bool(store.get("app", "start_minimized", default=False)))
        self.minimized.toggled.connect(lambda v: store.set("app", "start_minimized", value=v))
        self.auto_profile = QCheckBox("Profile automatisch je nach aktivem Programm wechseln")
        self.auto_profile.setChecked(bool(store.get("app", "auto_profile_switch", default=True)))
        self.auto_profile.toggled.connect(lambda v: store.set("app", "auto_profile_switch", value=v))
        for w in (self.tray, self.autostart, self.minimized, self.auto_profile):
            lay.addWidget(w)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Darstellung"))
        self.theme = QComboBox()
        for code, label in THEMES:
            self.theme.addItem(label, code)
        self.theme.setCurrentIndex(max(0, self.theme.findData(store.get("app", "theme", default="system"))))
        self.theme.activated.connect(self._set_theme)
        theme_row.addWidget(self.theme)
        theme_row.addStretch(1)
        lay.addLayout(theme_row)
        root.addWidget(box)

        # ---------------------------------------------------- Home Assistant
        box = QGroupBox("Home Assistant")
        form = QFormLayout(box)
        self.ha_host = QLineEdit(store.get("home_assistant", "host", default=""))
        self.ha_host.setPlaceholderText("http://homeassistant.local:8123")
        self.ha_token = QLineEdit(store.get("home_assistant", "token", default=""))
        self.ha_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.ha_token.setPlaceholderText("Langlebiges Zugriffstoken (Profil → Sicherheit)")
        form.addRow("Adresse", self.ha_host)
        form.addRow("Token", self.ha_token)
        row = QHBoxLayout()
        save = QPushButton("Speichern")
        save.clicked.connect(self._save_ha)
        test = QPushButton("Verbindung testen")
        test.clicked.connect(self._test_ha)
        row.addWidget(save)
        row.addWidget(test)
        row.addStretch(1)
        form.addRow("", row)
        root.addWidget(box)

        # ---------------------------------------------------- Info
        box = QGroupBox("Info")
        lay = QVBoxLayout(box)
        info = QLabel(f"Console Deck Pro – PC-App {__version__}<br>Daten: <a href='file:///{APP_DIR}'>{APP_DIR}</a>")
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setOpenExternalLinks(False)
        info.linkActivated.connect(lambda _: os.startfile(APP_DIR))
        lay.addWidget(info)
        root.addWidget(box)
        root.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._load_ports()

    def _load_ports(self) -> None:
        current = self.store.get("serial", "port")
        self.port.clear()
        self.port.addItem("— kein Port —", None)
        for dev, desc in available_ports():
            self.port.addItem(f"{dev}  –  {desc}" if desc != dev else dev, dev)
        if current and self.port.findData(current) < 0:
            self.port.addItem(f"{current}  (nicht gefunden)", current)
        self.port.setCurrentIndex(max(0, self.port.findData(current)))

    def _save_serial(self) -> None:
        self.store.set("serial", value={"port": self.port.currentData(), "baud_rate": self.baud.currentData()})
        self.serial.reconnect()

    def _set_autostart(self, enabled: bool) -> None:
        if autostart.set_enabled(enabled):
            self.store.set("app", "autostart", value=enabled)
        else:
            self.autostart.blockSignals(True)
            self.autostart.setChecked(not enabled)
            self.autostart.blockSignals(False)
            QMessageBox.warning(self, "Autostart", "Autostart konnte nicht geändert werden (siehe Protokoll).")

    def _set_theme(self) -> None:
        mode = self.theme.currentData()
        self.store.set("app", "theme", value=mode)
        apply_theme(mode)

    def _save_ha(self) -> None:
        self.store.set("home_assistant", value={"host": self.ha_host.text().strip().rstrip("/"),
                                                "token": self.ha_token.text().strip()})

    def _test_ha(self) -> None:
        import requests

        self._save_ha()
        host, token = self.ha_host.text().strip().rstrip("/"), self.ha_token.text().strip()
        try:
            r = requests.get(f"{host}/api/", headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if r.status_code == 200:
                QMessageBox.information(self, "Home Assistant", "Verbindung erfolgreich ✔")
            elif r.status_code == 401:
                QMessageBox.warning(self, "Home Assistant", "Token ungültig (HTTP 401).")
            else:
                QMessageBox.warning(self, "Home Assistant", f"Unerwartete Antwort: HTTP {r.status_code}")
        except requests.RequestException as exc:
            QMessageBox.warning(self, "Home Assistant", f"Keine Verbindung:\n{exc}")
