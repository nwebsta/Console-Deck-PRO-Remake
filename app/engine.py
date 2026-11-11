"""Verbindet Geräte-Eingaben mit den Aktionen des aktiven Profils."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from .actions import ActionExecutor, ActionRegistry, RunContext
from .device.protocol import InputEvent

log = logging.getLogger(__name__)

RELATIVE_THRESHOLD = 3  # % Bewegung, ab der Slider "hoch/runter" auslösen

# (Gruppen-ID, Titel, Modul-ID oder None, [(Eingabe, Beschriftung)])
INPUT_GROUPS: list[tuple[str, str, int | None, list[tuple[str, str]]]] = [
    ("main", "Hauptdeck", None, [(f"btn_{i}", f"Taste {i}") for i in range(1, 10)]),
    ("encoder", "Drehregler", None, [
        ("enc_ccw", "Links drehen"), ("enc_click", "Drücken"), ("enc_cw", "Rechts drehen")]),
    ("ext", "Modul: Zusatztasten", 1, [(f"ext_btn_{i}", f"Taste {i}") for i in range(1, 7)]),
    ("sliders", "Modul: Slider", 2, [
        ("slider_1", "Slider 1 – Position"), ("slider_1_up", "Slider 1 – hoch"), ("slider_1_down", "Slider 1 – runter"),
        ("slider_2", "Slider 2 – Position"), ("slider_2_up", "Slider 2 – hoch"), ("slider_2_down", "Slider 2 – runter")]),
    ("knobs", "Modul: Potis", 3, [
        ("knob_1", "Poti 1 – Position"), ("knob_1_cw", "Poti 1 – rechts"), ("knob_1_ccw", "Poti 1 – links"),
        ("knob_2", "Poti 2 – Position"), ("knob_2_cw", "Poti 2 – rechts"), ("knob_2_ccw", "Poti 2 – links")]),
]
ANALOG_INPUTS = {"slider_1", "slider_2", "knob_1", "knob_2"}
INPUT_LABELS = {key: f"{title.replace('Modul: ', '')} · {label}"
                for _, title, _, items in INPUT_GROUPS for key, label in items}


class Engine(QObject):
    input_event = Signal(object)  # InputEvent – für die Live-Anzeige

    def __init__(self, store, registry: ActionRegistry):
        super().__init__()
        self.store = store
        self.registry = registry
        self.executor = ActionExecutor(registry).start()
        self._rel_last: dict[str, float] = {}

    def stop(self) -> None:
        self.executor.stop()

    def handle(self, ev: InputEvent) -> None:
        self.input_event.emit(ev)
        if ev.kind == "press":
            self.fire(ev.key)
        elif ev.kind == "rotate":
            # Die Firmware zählt 2 Schritte pro Rastung.
            self.fire("enc_cw" if ev.delta > 0 else "enc_ccw", multiplier=max(0.5, abs(ev.delta) / 2))
        elif ev.kind == "analog":
            self._analog(ev.key, ev.value or 0.0)
        elif ev.kind == "module":
            self._rel_last.clear()

    def fire(self, key: str, **ctx) -> None:
        mapping = self.store.mapping(key)
        if mapping:
            self.executor.submit(mapping, RunContext(input_key=key, engine=self, **ctx))

    def _analog(self, key: str, value: float) -> None:
        mapping = self.store.mapping(key)
        at = self.registry.get(mapping.get("action")) if mapping else None
        if mapping and at and at.analog:
            self.executor.submit_analog(key, mapping, RunContext(input_key=key, value=value, engine=self))
            return
        last = self._rel_last.get(key)
        if last is None:
            self._rel_last[key] = value
            return
        diff = value - last
        if abs(diff) >= RELATIVE_THRESHOLD:
            self._rel_last[key] = value
            up, down = ("up", "down") if key.startswith("slider") else ("cw", "ccw")
            self.fire(f"{key}_{up if diff > 0 else down}")

    def test(self, mapping: dict) -> None:
        """Aktion aus der Oberfläche heraus ausprobieren."""
        self.executor.submit(mapping, RunContext(input_key="test", engine=self))
