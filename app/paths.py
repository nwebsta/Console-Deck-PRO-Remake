"""Zentrale Pfade der App."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ConsoleDeckPro"
IS_FROZEN = bool(getattr(sys, "frozen", False))


def _app_dir() -> Path:
    override = os.getenv("CONSOLE_DECK_PRO_DIR")
    if override:
        base = Path(override)
    else:
        appdata = os.getenv("APPDATA")
        base = (Path(appdata) if appdata else Path.home() / "AppData" / "Roaming") / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


APP_DIR = _app_dir()
SETTINGS_FILE = APP_DIR / "settings.json"
LEGACY_CONFIG_FILE = APP_DIR / "config.json"  # Config der alten Python/Flutter-App
PLUGINS_DIR = APP_DIR / "plugins"
LOG_DIR = APP_DIR / "logs"

PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def dev_plugin_dirs() -> list[Path]:
    """Im Entwicklungsmodus werden zusätzlich die Module aus dem Repo geladen."""
    if IS_FROZEN:
        return []
    repo_plugins = PROJECT_ROOT / "plugins"
    return [repo_plugins] if repo_plugins.is_dir() else []
