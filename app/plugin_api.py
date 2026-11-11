"""Öffentliche Schnittstelle für Module (Plugins).

Ein Modul ist ein Ordner mit ``plugin.json`` und ``__init__.py``. Die
``__init__.py`` stellt eine Funktion ``register(api: PluginAPI)`` bereit::

    from app.plugin_api import Param

    def register(api):
        api.register_action("hello", "Hallo sagen",
                            lambda mapping, ctx: api.log.info("Hallo!"))

Siehe docs/MODULE.md für die vollständige Beschreibung.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import QTimer

from .actions.base import ActionType, ChoiceList, Param, RunContext

if TYPE_CHECKING:
    from .plugins import PluginInfo, PluginManager

API_VERSION = 1

__all__ = ["API_VERSION", "ChoiceList", "Param", "PluginAPI", "RunContext"]


class PluginAPI:
    def __init__(self, manager: "PluginManager", info: "PluginInfo"):
        self._manager = manager
        self._info = info
        self.id = info.id
        self.log = logging.getLogger(f"modul.{info.id}")
        self._unload_hooks: list[Callable[[], None]] = []
        self._settings_hook: Callable[[dict], None] | None = None

    # ------------------------------------------------------------------ Aktionen
    def register_action(
        self,
        action_id: str,
        name: str,
        run: Callable[[dict, RunContext], None],
        params: list[Param] | None = None,
        *,
        category: str | None = None,
        analog: bool = False,
        threaded: bool = False,
        description: str = "",
        summary: Callable[[dict], str] | None = None,
    ) -> str:
        """Registriert eine Aktion. Die gespeicherte ID lautet ``<modul-id>.<action_id>``."""
        full_id = f"{self.id}.{action_id}"
        self._manager.registry.register(ActionType(
            id=full_id, name=name, run=run, params=list(params or []),
            category=category or self._info.name, analog=analog, threaded=threaded,
            description=description, source=self.id, summary=summary,
        ))
        return full_id

    # ------------------------------------------------------------------ Einstellungen
    def register_settings(self, params: list[Param], on_change: Callable[[dict], None] | None = None) -> None:
        """Einstellungsfelder, die auf der Seite *Module* angezeigt werden."""
        self._info.settings_params = list(params)
        self._settings_hook = on_change

    @property
    def settings(self) -> dict:
        values = {p.key: p.default for p in self._info.settings_params}
        values.update(self._manager.store.plugin_settings(self.id))
        return values

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def save_settings(self, values: dict) -> None:
        self._manager.store.set_plugin_settings(self.id, values)
        if self._settings_hook:
            try:
                self._settings_hook(self.settings)
            except Exception:
                self.log.exception("Fehler beim Übernehmen der Einstellungen")

    # ------------------------------------------------------------------ Sonstiges
    def set_status(self, text: str) -> None:
        """Kurzer Status (z. B. "Verbunden"), der in der Modulliste erscheint."""
        self._info.status = text
        self._manager.status_changed.emit(self.id)

    def on_unload(self, fn: Callable[[], None]) -> None:
        self._unload_hooks.append(fn)

    def run_in_gui(self, fn: Callable[[], None]) -> None:
        """Führt ``fn`` im GUI-Thread aus (für Qt-Objekte)."""
        QTimer.singleShot(0, self._manager, fn)

    def _unload(self) -> None:
        for fn in reversed(self._unload_hooks):
            try:
                fn()
            except Exception:
                self.log.exception("Fehler beim Entladen")
        self._unload_hooks.clear()
