"""Windows-Autostart über HKCU\\...\\Run."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from .paths import APP_NAME, IS_FROZEN, PROJECT_ROOT

log = logging.getLogger(__name__)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def command() -> str:
    if IS_FROZEN:
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{exe}" "{PROJECT_ROOT / "app" / "__main__.py"}" --minimized'


def _current() -> str | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, APP_NAME)[0]
    except OSError:
        return None


def is_enabled() -> bool:
    return _current() is not None


def set_enabled(enabled: bool) -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError as exc:
        log.error("Autostart konnte nicht geändert werden: %s", exc)
        return False


def sync(enabled: bool) -> None:
    """Hält den Registry-Eintrag aktuell (z. B. wenn die .exe verschoben wurde)."""
    if enabled and _current() != command():
        set_enabled(True)
    elif not enabled and is_enabled():
        set_enabled(False)
