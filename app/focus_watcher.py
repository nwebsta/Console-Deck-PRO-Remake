"""Automatischer Profilwechsel je nach Programm im Vordergrund."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

import psutil


def foreground_exe() -> str | None:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        return psutil.Process(pid.value).name().lower()
    except (psutil.Error, ValueError):
        return None


class AutoProfileSwitcher:
    def __init__(self, store, interval: float = 1.0):
        self._store = store
        self._interval = interval
        self._stop = threading.Event()
        self._last_exe: str | None = None
        self._thread = threading.Thread(target=self._run, name="focus-watcher", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        own = psutil.Process().name().lower()
        while not self._stop.wait(self._interval):
            if not self._store.get("app", "auto_profile_switch", default=True):
                if self._store.is_auto_profile:
                    self._store.set_active_profile(self._store.manual_profile)
                continue
            exe = foreground_exe()
            if not exe or exe == own or exe == self._last_exe:
                continue
            self._last_exe = exe
            target = self._store.profile_for_app(exe)
            if target:
                self._store.set_active_profile(target, auto=True)
            elif self._store.is_auto_profile:
                self._store.set_active_profile(self._store.manual_profile)
