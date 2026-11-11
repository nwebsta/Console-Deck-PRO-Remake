"""Einstellungen und Profile (settings.json)."""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from .paths import LEGACY_CONFIG_FILE, SETTINGS_FILE

log = logging.getLogger(__name__)

SETTINGS_VERSION = 2

DEFAULT_ENCODER = {
    "enc_click": {"action": "toggle_mute"},
    "enc_cw": {"action": "change_volume", "value": 2},
    "enc_ccw": {"action": "change_volume", "value": -2},
}


def default_settings() -> dict:
    return {
        "version": SETTINGS_VERSION,
        "serial": {"port": None, "baud_rate": 115200},
        "language": "de",  # bestimmt das Datumsformat auf dem Display
        "app": {
            "minimize_to_tray": True,
            "start_minimized": False,
            "autostart": False,
            "theme": "system",
            "auto_profile_switch": True,
            "tray_hint_shown": False,
        },
        "home_assistant": {"host": "", "token": ""},
        "active_profile": "Standard",
        "profiles": [new_profile("Standard")],
        "plugins": {"disabled": [], "settings": {}},
    }


def new_profile(name: str) -> dict:
    return {"name": name, "apps": [], "mappings": copy.deepcopy(DEFAULT_ENCODER)}


def _merge_defaults(data: dict, defaults: dict) -> dict:
    for key, value in defaults.items():
        if key not in data:
            data[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(data[key], dict) and key != "settings":
            _merge_defaults(data[key], value)
    return data


def migrate_legacy(old: dict) -> dict:
    """Übernimmt die config.json der bisherigen App in ein Standard-Profil."""
    data = default_settings()
    serial = old.get("serial")
    if isinstance(serial, dict):
        for key in ("port", "baud_rate"):
            if serial.get(key):
                data["serial"][key] = serial[key]
    if old.get("language"):
        data["language"] = old["language"]
    if isinstance(old.get("home_assistant"), dict):
        data["home_assistant"].update(
            {k: v for k, v in old["home_assistant"].items() if k in ("host", "token")}
        )

    raw = old.get("mappings") if isinstance(old.get("mappings"), dict) else {}
    flat: dict = {}
    if "main" in raw or "modules" in raw:
        for part in ("main", "modules"):
            if isinstance(raw.get(part), dict):
                flat.update(raw[part])
    else:
        flat.update(raw)

    mappings = data["profiles"][0]["mappings"]
    for key, mapping in flat.items():
        if isinstance(mapping, dict) and mapping.get("action"):
            mappings[key] = mapping
    return data


class ConfigStore(QObject):
    """Thread-sichere Verwaltung der Einstellungen.

    Das *aktive* Profil kann zur Laufzeit automatisch (je nach Vordergrund-App)
    wechseln; gespeichert wird nur das manuell gewählte Profil.
    """

    changed = Signal()
    profiles_changed = Signal()
    active_profile_changed = Signal(str, bool)  # name, automatisch

    def __init__(self, path: Path = SETTINGS_FILE):
        super().__init__()
        self._path = path
        self._lock = threading.RLock()
        self.data = self._load()
        self._current_profile = self._valid_profile(self.data.get("active_profile"))
        self._auto_active = False

    # ------------------------------------------------------------------ Laden/Speichern
    def _load(self) -> dict:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8") or "{}")
                if not isinstance(data, dict):
                    raise ValueError("Wurzel ist kein Objekt")
            except (ValueError, OSError) as exc:
                backup = self._path.with_suffix(f".bad.{int(time.time())}.json")
                log.error("settings.json ist beschädigt (%s) – Sicherung: %s", exc, backup)
                try:
                    os.replace(self._path, backup)
                except OSError:
                    pass
                data = default_settings()
            data = _merge_defaults(data, default_settings())
            if not data["profiles"]:
                data["profiles"] = [new_profile("Standard")]
        elif LEGACY_CONFIG_FILE.exists():
            try:
                old = json.loads(LEGACY_CONFIG_FILE.read_text(encoding="utf-8") or "{}")
                data = migrate_legacy(old if isinstance(old, dict) else {})
                log.info("Konfiguration der bisherigen App übernommen: %s", LEGACY_CONFIG_FILE)
            except (ValueError, OSError) as exc:
                log.warning("Alte config.json konnte nicht gelesen werden: %s", exc)
                data = default_settings()
        else:
            data = default_settings()
        self._write(data)
        return data

    def _write(self, data: dict) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)

    def save(self) -> None:
        with self._lock:
            try:
                self._write(self.data)
            except OSError as exc:
                log.error("Einstellungen konnten nicht gespeichert werden: %s", exc)
        self.changed.emit()

    # ------------------------------------------------------------------ Allgemein
    def get(self, *path: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self.data
            for key in path:
                if not isinstance(node, dict) or key not in node:
                    return default
                node = node[key]
            return copy.deepcopy(node)

    def set(self, *path: str, value: Any) -> None:
        with self._lock:
            node = self.data
            for key in path[:-1]:
                node = node.setdefault(key, {})
            node[path[-1]] = value
        self.save()

    # ------------------------------------------------------------------ Profile
    def _valid_profile(self, name: str | None) -> str:
        names = self.profile_names()
        return name if name in names else names[0]

    def profile_names(self) -> list[str]:
        with self._lock:
            return [p["name"] for p in self.data["profiles"]]

    def _profile(self, name: str) -> dict | None:
        for p in self.data["profiles"]:
            if p["name"] == name:
                return p
        return None

    def profile(self, name: str) -> dict | None:
        with self._lock:
            p = self._profile(name)
            return copy.deepcopy(p) if p else None

    @property
    def current_profile(self) -> str:
        return self._current_profile

    @property
    def manual_profile(self) -> str:
        return self._valid_profile(self.data.get("active_profile"))

    @property
    def is_auto_profile(self) -> bool:
        return self._auto_active

    def set_active_profile(self, name: str, auto: bool = False) -> None:
        with self._lock:
            if self._profile(name) is None:
                return
            if not auto:
                self.data["active_profile"] = name
            changed = name != self._current_profile or auto != self._auto_active
            self._current_profile = name
            self._auto_active = auto
        if not auto:
            self.save()
        if changed:
            log.info("Aktives Profil: %s%s", name, " (automatisch)" if auto else "")
            self.active_profile_changed.emit(name, auto)

    def cycle_profile(self, step: int = 1) -> None:
        names = self.profile_names()
        idx = names.index(self._current_profile) if self._current_profile in names else 0
        self.set_active_profile(names[(idx + step) % len(names)])

    def add_profile(self, name: str, copy_from: str | None = None) -> bool:
        with self._lock:
            if not name or self._profile(name):
                return False
            src = self._profile(copy_from) if copy_from else None
            prof = copy.deepcopy(src) if src else new_profile(name)
            prof["name"] = name
            if src:
                prof["apps"] = []
            self.data["profiles"].append(prof)
        self.save()
        self.profiles_changed.emit()
        return True

    def rename_profile(self, old: str, new: str) -> bool:
        with self._lock:
            prof = self._profile(old)
            if not prof or not new or self._profile(new):
                return False
            prof["name"] = new
            if self.data.get("active_profile") == old:
                self.data["active_profile"] = new
            if self._current_profile == old:
                self._current_profile = new
        self.save()
        self.profiles_changed.emit()
        self.active_profile_changed.emit(self._current_profile, self._auto_active)
        return True

    def delete_profile(self, name: str) -> bool:
        with self._lock:
            if len(self.data["profiles"]) <= 1:
                return False
            self.data["profiles"] = [p for p in self.data["profiles"] if p["name"] != name]
            fallback = self.data["profiles"][0]["name"]
            if self.data.get("active_profile") == name:
                self.data["active_profile"] = fallback
            switch = self._current_profile == name
        self.save()
        self.profiles_changed.emit()
        if switch:
            self.set_active_profile(self.manual_profile)
        return True

    def set_profile_apps(self, name: str, apps: list[str]) -> None:
        with self._lock:
            prof = self._profile(name)
            if prof is None:
                return
            prof["apps"] = [a.strip().lower() for a in apps if a.strip()]
        self.save()

    def profile_for_app(self, exe_name: str) -> str | None:
        exe_name = exe_name.lower()
        with self._lock:
            for p in self.data["profiles"]:
                if exe_name in p.get("apps", []):
                    return p["name"]
        return None

    # ------------------------------------------------------------------ Belegungen
    def mapping(self, key: str, profile: str | None = None) -> dict | None:
        with self._lock:
            prof = self._profile(profile or self._current_profile)
            if not prof:
                return None
            m = prof["mappings"].get(key)
            return copy.deepcopy(m) if isinstance(m, dict) and m.get("action") else None

    def set_mapping(self, key: str, mapping: dict | None, profile: str | None = None) -> None:
        with self._lock:
            prof = self._profile(profile or self._current_profile)
            if prof is None:
                return
            if mapping:
                prof["mappings"][key] = mapping
            else:
                prof["mappings"].pop(key, None)
        self.save()

    # ------------------------------------------------------------------ Module
    def plugin_settings(self, plugin_id: str) -> dict:
        return self.get("plugins", "settings", plugin_id, default={}) or {}

    def set_plugin_settings(self, plugin_id: str, values: dict) -> None:
        with self._lock:
            self.data["plugins"]["settings"][plugin_id] = values
        self.save()

    def plugin_enabled(self, plugin_id: str) -> bool:
        return plugin_id not in (self.get("plugins", "disabled", default=[]) or [])

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        with self._lock:
            disabled = set(self.data["plugins"].get("disabled", []))
            (disabled.discard if enabled else disabled.add)(plugin_id)
            self.data["plugins"]["disabled"] = sorted(disabled)
        self.save()
