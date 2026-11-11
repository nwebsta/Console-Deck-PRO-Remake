"""Grundbausteine für Aktionen – werden auch von Modulen (Plugins) genutzt."""

from __future__ import annotations

import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)

ChoiceList = list[tuple[str, str]]  # (gespeicherter Wert, Anzeigename)


@dataclass
class Param:
    """Ein Eingabefeld einer Aktion oder einer Modul-Einstellung.

    kind: text | url | password | multiline | int | bool | file | app | hotkey | choice
    """

    key: str
    label: str
    kind: str = "text"
    default: Any = None
    choices: ChoiceList | Callable[[], ChoiceList] | None = None
    help: str = ""
    minimum: int = -1000
    maximum: int = 1000

    def get_choices(self) -> ChoiceList:
        try:
            return list(self.choices() if callable(self.choices) else (self.choices or []))
        except Exception as exc:  # dynamische Listen dürfen die UI nicht abstürzen lassen
            log.warning("Auswahlliste für %s nicht verfügbar: %s", self.key, exc)
            return []


@dataclass
class RunContext:
    """Informationen zur Auslösung einer Aktion."""

    input_key: str = ""
    value: float | None = None  # Position 0–100 bei Slidern/Potis
    multiplier: float = 1.0  # Encoder: Anzahl Rastungen
    engine: Any = None


@dataclass
class ActionType:
    id: str
    name: str
    run: Callable[[dict, RunContext], None]
    category: str = "Allgemein"
    params: list[Param] = field(default_factory=list)
    analog: bool = False  # versteht eine Position 0–100 (Slider/Poti)
    threaded: bool = False  # langsam (Netzwerk) → eigener Thread
    description: str = ""
    source: str = "builtin"
    summary: Callable[[dict], str] | None = None

    def describe(self, mapping: dict) -> str:
        if self.summary:
            try:
                return self.summary(mapping)
            except Exception:
                pass
        for p in self.params:
            val = mapping.get(p.key)
            if val in (None, "", []):
                continue
            if p.kind == "password":
                return self.name
            if p.kind == "hotkey" and isinstance(val, list):
                val = "+".join(val).upper()
            if p.kind == "choice":
                val = dict(p.get_choices()).get(str(val), val)
            if p.kind in ("file", "app"):
                val = str(val).replace("\\", "/").rsplit("/", 1)[-1]
            return f"{self.name}: {val}"
        return self.name


class ActionRegistry:
    def __init__(self) -> None:
        self._types: dict[str, ActionType] = {}
        self._lock = threading.Lock()
        self.listeners: list[Callable[[], None]] = []

    def register(self, action: ActionType) -> None:
        with self._lock:
            self._types[action.id] = action
        self._notify()

    def unregister_source(self, source: str) -> None:
        with self._lock:
            self._types = {k: v for k, v in self._types.items() if v.source != source}
        self._notify()

    def get(self, action_id: str | None) -> ActionType | None:
        return self._types.get(action_id or "")

    def all(self) -> list[ActionType]:
        with self._lock:
            items = list(self._types.values())
        return sorted(items, key=lambda a: (a.source != "builtin", a.category, a.name))

    def describe(self, mapping: dict | None) -> str:
        if not mapping:
            return ""
        at = self.get(mapping.get("action"))
        return at.describe(mapping) if at else f"Unbekannt: {mapping.get('action')}"

    def _notify(self) -> None:
        for fn in list(self.listeners):
            try:
                fn()
            except Exception:
                log.exception("Registry-Listener fehlgeschlagen")


class ActionExecutor:
    """Führt Aktionen im Hintergrund aus, damit das Gerät nie blockiert.

    Slider-/Poti-Werte werden zusammengefasst: Es zählt immer nur die
    letzte Position, ältere Werte werden verworfen.
    """

    def __init__(self, registry: ActionRegistry):
        self.registry = registry
        self._q: queue.Queue = queue.Queue(maxsize=256)
        self._analog: dict[str, tuple[dict, RunContext]] = {}
        self._analog_lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="action")
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="action-executor", daemon=True)

    def start(self) -> "ActionExecutor":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._pool.shutdown(wait=False, cancel_futures=True)

    def submit(self, mapping: dict | None, ctx: RunContext) -> None:
        if mapping:
            self._put(("single", mapping, ctx))

    def submit_analog(self, key: str, mapping: dict, ctx: RunContext) -> None:
        with self._analog_lock:
            pending = key in self._analog
            self._analog[key] = (mapping, ctx)
        if not pending:
            self._put(("analog", key, None))

    def _put(self, item) -> None:
        try:
            self._q.put_nowait(item)
        except queue.Full:
            log.warning("Aktions-Warteschlange voll – Eingabe verworfen")

    def _run(self) -> None:
        try:  # COM für Lautstärke (pycaw) in diesem Thread initialisieren
            import comtypes

            comtypes.CoInitialize()
        except Exception:
            pass
        while not self._stop.is_set():
            try:
                kind, a, b = self._q.get(timeout=0.25)
            except queue.Empty:
                continue
            if kind == "analog":
                with self._analog_lock:
                    item = self._analog.pop(a, None)
                if item:
                    self.execute(*item)
            else:
                self.execute(a, b)

    def execute(self, mapping: dict, ctx: RunContext) -> None:
        at = self.registry.get(mapping.get("action"))
        if at is None:
            log.warning("Unbekannte Aktion '%s' (Modul nicht installiert?)", mapping.get("action"))
            return
        if at.threaded:
            self._pool.submit(self._safe_run, at, mapping, ctx)
        else:
            self._safe_run(at, mapping, ctx)

    @staticmethod
    def _safe_run(at: ActionType, mapping: dict, ctx: RunContext) -> None:
        try:
            log.debug("Aktion %s (%s)", at.id, ctx.input_key)
            at.run(mapping, ctx)
        except Exception as exc:
            log.error("Aktion '%s' fehlgeschlagen: %s", at.name, exc)
