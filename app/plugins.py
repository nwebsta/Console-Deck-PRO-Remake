"""Laden, Installieren und Entfernen von Modulen."""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QObject, Signal

from .actions.base import ActionRegistry, Param
from .paths import PLUGINS_DIR, dev_plugin_dirs
from .plugin_api import API_VERSION, PluginAPI

log = logging.getLogger(__name__)
ID_RE = re.compile(r"^[a-z0-9_\-]{2,40}$")


class PluginError(Exception):
    pass


@dataclass
class PluginInfo:
    id: str
    name: str
    version: str
    path: Path
    description: str = ""
    author: str = ""
    entry: str = "__init__.py"
    api_version: int = 1
    dev: bool = False  # aus dem Repo geladen (Entwicklungsmodus)
    loaded: bool = False
    error: str = ""
    status: str = ""
    settings_params: list[Param] = field(default_factory=list)
    api: PluginAPI | None = None

    @property
    def module_name(self) -> str:
        return f"cdp_plugin_{self.id.replace('-', '_')}"


def read_manifest(folder: Path) -> PluginInfo:
    manifest = folder / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PluginError(f"plugin.json nicht lesbar: {exc}") from exc
    pid = str(data.get("id", "")).strip().lower()
    if not ID_RE.match(pid):
        raise PluginError(f"Ungültige Modul-ID '{pid}' (erlaubt: a-z, 0-9, _ und -)")
    return PluginInfo(
        id=pid,
        name=str(data.get("name") or pid),
        version=str(data.get("version") or "0.0.0"),
        description=str(data.get("description") or ""),
        author=str(data.get("author") or ""),
        entry=str(data.get("entry") or "__init__.py"),
        api_version=int(data.get("api_version") or 1),
        path=folder,
    )


class PluginManager(QObject):
    plugins_changed = Signal()
    status_changed = Signal(str)

    def __init__(self, store, registry: ActionRegistry):
        super().__init__()
        self.store = store
        self.registry = registry
        self.plugins: dict[str, PluginInfo] = {}

    # ------------------------------------------------------------------ Erkennen/Laden
    def discover(self) -> None:
        found: dict[str, PluginInfo] = {}
        sources = [(PLUGINS_DIR, False)] + [(d, True) for d in dev_plugin_dirs()]
        for base, dev in sources:
            for folder in sorted(p for p in base.iterdir() if p.is_dir()):
                if not (folder / "plugin.json").exists():
                    continue
                try:
                    info = read_manifest(folder)
                except PluginError as exc:
                    log.error("Modul in %s übersprungen: %s", folder, exc)
                    continue
                if info.id in found:
                    continue  # installierte Version hat Vorrang vor der Repo-Version
                info.dev = dev
                old = self.plugins.get(info.id)
                if old and old.loaded:
                    found[info.id] = old
                else:
                    found[info.id] = info
        self.plugins = found

    def load_all(self) -> None:
        self.discover()
        for info in self.plugins.values():
            if self.store.plugin_enabled(info.id) and not info.loaded:
                self.load(info)
        self.plugins_changed.emit()

    def load(self, info: PluginInfo) -> bool:
        info.error = ""
        if info.api_version > API_VERSION:
            info.error = f"Benötigt eine neuere App-Version (API {info.api_version})"
            log.error("Modul %s: %s", info.id, info.error)
            return False
        entry = info.path / info.entry
        if not entry.is_file():
            info.error = f"Einstiegsdatei {info.entry} fehlt"
            return False
        lib = info.path / "lib"  # mitgelieferte reine Python-Bibliotheken
        if lib.is_dir() and str(lib) not in sys.path:
            sys.path.insert(0, str(lib))
        try:
            spec = importlib.util.spec_from_file_location(
                info.module_name, entry, submodule_search_locations=[str(info.path)])
            if spec is None or spec.loader is None:
                raise PluginError("Modul konnte nicht importiert werden")
            module = importlib.util.module_from_spec(spec)
            sys.modules[info.module_name] = module
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if not callable(register):
                raise PluginError("Funktion register(api) fehlt")
            info.api = PluginAPI(self, info)
            register(info.api)
        except Exception as exc:
            info.error = str(exc) or exc.__class__.__name__
            log.exception("Modul %s konnte nicht geladen werden", info.id)
            self._cleanup(info)
            return False
        info.loaded = True
        log.info("Modul geladen: %s %s", info.name, info.version)
        return True

    def unload(self, info: PluginInfo) -> None:
        if info.api:
            info.api._unload()
        self._cleanup(info)
        info.loaded = False
        info.status = ""

    def _cleanup(self, info: PluginInfo) -> None:
        self.registry.unregister_source(info.id)
        info.api = None
        for name in [n for n in sys.modules if n == info.module_name or n.startswith(info.module_name + ".")]:
            del sys.modules[name]

    def unload_all(self) -> None:
        for info in self.plugins.values():
            if info.loaded:
                self.unload(info)

    # ------------------------------------------------------------------ Verwalten
    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        info = self.plugins.get(plugin_id)
        if not info:
            return
        self.store.set_plugin_enabled(plugin_id, enabled)
        if enabled and not info.loaded:
            self.load(info)
        elif not enabled and info.loaded:
            self.unload(info)
        self.plugins_changed.emit()

    def install_zip(self, zip_path: str | Path) -> PluginInfo:
        zip_path = Path(zip_path)
        with tempfile.TemporaryDirectory(prefix="cdp_plugin_") as tmp:
            tmp_dir = Path(tmp)
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    for member in zf.infolist():
                        rel = PurePosixPath(member.filename)
                        if rel.is_absolute() or ".." in rel.parts:
                            raise PluginError(f"Unsicherer Pfad im Archiv: {member.filename}")
                    zf.extractall(tmp_dir)
            except zipfile.BadZipFile as exc:
                raise PluginError("Die Datei ist kein gültiges ZIP-Archiv") from exc

            root = tmp_dir
            if not (root / "plugin.json").exists():
                subdirs = [p for p in tmp_dir.iterdir() if p.is_dir() and (p / "plugin.json").exists()]
                if len(subdirs) != 1:
                    raise PluginError("Im Archiv wurde keine plugin.json gefunden")
                root = subdirs[0]
            info = read_manifest(root)

            existing = self.plugins.get(info.id)
            if existing and existing.loaded:
                self.unload(existing)
            target = PLUGINS_DIR / info.id
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(root, target, ignore=shutil.ignore_patterns("__pycache__"))

        log.info("Modul installiert: %s %s", info.name, info.version)
        self.discover()
        info = self.plugins[info.id]
        self.store.set_plugin_enabled(info.id, True)
        self.load(info)
        self.plugins_changed.emit()
        return info

    def remove(self, plugin_id: str) -> None:
        info = self.plugins.get(plugin_id)
        if not info:
            return
        if info.dev:
            raise PluginError("Module aus dem Projektordner können nicht entfernt werden")
        if info.loaded:
            self.unload(info)
        target = info.path.resolve()
        if PLUGINS_DIR.resolve() not in target.parents:
            raise PluginError("Modul liegt außerhalb des Modulordners")
        shutil.rmtree(target, ignore_errors=True)
        self.store.set_plugin_settings(plugin_id, {})
        log.info("Modul entfernt: %s", info.name)
        self.discover()
        self.plugins_changed.emit()
