"""Einstiegspunkt der App."""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from . import __version__, autostart
from .actions import ActionRegistry
from .actions.builtin import register_builtin
from .actions.system import AudioPlayer
from .config import ConfigStore
from .device.serial_worker import SerialWorker
from .engine import Engine
from .focus_watcher import AutoProfileSwitcher
from .paths import APP_NAME, LOG_DIR
from .plugins import PluginManager
from .ui.icon import app_icon
from .ui.log_page import QtLogHandler
from .ui.main_window import MainWindow
from .ui.theme import setup_style

log = logging.getLogger("app")


def setup_logging() -> QtLogHandler:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(fh)
    if sys.stderr is not None:  # in der .exe gibt es keine Konsole
        root.addHandler(logging.StreamHandler())
    qt = QtLogHandler()
    root.addHandler(qt)
    sys.excepthook = lambda t, v, tb: log.critical("Unbehandelter Fehler", exc_info=(t, v, tb))
    return qt


def _instance_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return f"{APP_NAME}-{user}"


def _notify_running_instance() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(_instance_name())
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def run() -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--minimized", action="store_true", help="nur im Tray starten")
    args, _ = parser.parse_known_args()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName("Console Deck Pro")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    if _notify_running_instance():
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(_instance_name())
    server.listen(_instance_name())

    log_handler = setup_logging()
    log.info("Console Deck Pro %s startet", __version__)

    store = ConfigStore()
    setup_style(app, store.get("app", "theme", default="system"))
    autostart.sync(bool(store.get("app", "autostart", default=False)))

    registry = ActionRegistry()
    audio = AudioPlayer()
    register_builtin(registry, store, audio)
    engine = Engine(store, registry)
    plugins = PluginManager(store, registry)
    plugins.load_all()
    serial_worker = SerialWorker(store, engine)
    switcher = AutoProfileSwitcher(store)

    window = MainWindow(store, registry, engine, plugins, serial_worker, log_handler)

    def on_new_connection() -> None:
        conn = server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(window.show_window)
    server.newConnection.connect(on_new_connection)

    def shutdown() -> None:
        log.info("Beende …")
        switcher.stop()
        serial_worker.stop()
        plugins.unload_all()
        engine.stop()
        server.close()
    app.aboutToQuit.connect(shutdown)

    serial_worker.start()
    switcher.start()
    start_hidden = args.minimized or bool(store.get("app", "start_minimized", default=False))
    if not start_hidden:
        window.show()
    return app.exec()
