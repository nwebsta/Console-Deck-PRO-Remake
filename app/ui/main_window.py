"""Hauptfenster und Tray-Symbol."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QStackedWidget,
    QSystemTrayIcon,
    QWidget,
)

from .. import __version__
from .deck_page import DeckPage
from .icon import app_icon
from .log_page import LogPage, QtLogHandler
from .plugins_page import PluginsPage
from .settings_page import SettingsPage

STATUS_TEXT = {"connected": "● Verbunden", "connecting": "◌ Verbinde …", "error": "○ Nicht verbunden",
               "no_port": "○ Kein Port gewählt"}


class MainWindow(QMainWindow):
    def __init__(self, store, registry, engine, plugins, serial_worker, log_handler: QtLogHandler) -> None:
        super().__init__()
        self.store = store
        self.serial = serial_worker
        self._quitting = False
        self._connected = False
        self.setWindowTitle("Console Deck Pro")
        self.setWindowIcon(app_icon())
        self.resize(1100, 760)

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(180)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        self.deck_page = DeckPage(store, registry, engine)
        pages = [("Deck", self.deck_page), ("Module", PluginsPage(plugins)),
                 ("Einstellungen", SettingsPage(store, serial_worker)), ("Protokoll", LogPage(log_handler))]
        for name, page in pages:
            self.nav.addItem(name)
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.conn_label = QLabel()
        self.module_label = QLabel()
        self.profile_label = QLabel()
        sb = self.statusBar()
        sb.addWidget(self.conn_label)
        sb.addWidget(self.module_label)
        sb.addPermanentWidget(self.profile_label)

        self._build_tray()
        serial_worker.status_changed.connect(self._on_status)
        engine.input_event.connect(self._on_input)
        store.active_profile_changed.connect(lambda *_: self._update_profile())
        store.profiles_changed.connect(self._update_profile)
        self._on_status(serial_worker.state, "")
        self._update_profile()

    # ------------------------------------------------------------------ Tray
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(app_icon(False), self)
        menu = QMenu()
        open_action = QAction("Öffnen", self)
        open_action.triggered.connect(self.show_window)
        menu.addAction(open_action)
        menu.addSeparator()
        self.profile_menu = menu.addMenu("Profil")
        menu.addSeparator()
        quit_action = QAction("Beenden", self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray)
        self.tray.show()

    def _on_tray(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_window()

    def _rebuild_profile_menu(self) -> None:
        self.profile_menu.clear()
        group = QActionGroup(self.profile_menu)
        for name in self.store.profile_names():
            act = QAction(name, self.profile_menu, checkable=True)
            act.setChecked(name == self.store.current_profile)
            act.triggered.connect(lambda _=False, n=name: self.store.set_active_profile(n))
            group.addAction(act)
            self.profile_menu.addAction(act)

    # ------------------------------------------------------------------ Status
    def _on_status(self, state: str, msg: str) -> None:
        self._connected = state == "connected"
        self.conn_label.setText(STATUS_TEXT.get(state, state))
        self.conn_label.setToolTip(msg)
        if not self._connected:
            self.module_label.setText("")
            self.deck_page.set_disconnected()
        self.tray.setIcon(app_icon(self._connected))
        self._update_tooltip()

    def _on_input(self, ev) -> None:
        if ev.kind == "module":
            self.module_label.setText(f"   Modul: {self.deck_page.module_name}")

    def _update_profile(self) -> None:
        auto = " (automatisch)" if self.store.is_auto_profile else ""
        self.profile_label.setText(f"Profil: {self.store.current_profile}{auto}")
        self._rebuild_profile_menu()
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        state = "verbunden" if self._connected else "nicht verbunden"
        self.tray.setToolTip(f"Console Deck Pro {__version__}\n{state} · Profil: {self.store.current_profile}")

    # ------------------------------------------------------------------ Fenster
    def show_window(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~self.windowState().WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._quitting and self.store.get("app", "minimize_to_tray", default=True) \
                and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            if not self.store.get("app", "tray_hint_shown", default=False):
                self.tray.showMessage("Console Deck Pro läuft weiter",
                                      "Die App ist jetzt im Infobereich. Beenden über Rechtsklick → Beenden.",
                                      app_icon(), 4000)
                self.store.set("app", "tray_hint_shown", value=True)
            return
        self._quitting = True
        event.accept()
        QApplication.instance().quit()

    def quit(self) -> None:
        self._quitting = True
        self.tray.hide()
        QApplication.instance().quit()
