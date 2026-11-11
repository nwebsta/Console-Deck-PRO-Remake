"""Serielles Protokoll des Console Deck Pro (Arduino-Firmware).

Gerät → PC (eine Zeile, ';'-getrennt):
    b1;…;b9;enc_click;enc_value;module_id[;modul-daten]
    module_id 1: 6 Werte (Zusatztasten) · 2: Slider (0–100 %) · 3: Potis (0–100 %)

PC → Gerät:
    BOOT:HH:MM:SS,TT.MM
    STATS:cpu,gpu,ram,cpu_mhz,gpu_temp,HH:MM:SS,TT.MM
"""

from __future__ import annotations

from dataclasses import dataclass, field

MODULE_NONE, MODULE_BUTTONS, MODULE_SLIDERS, MODULE_KNOBS = 0, 1, 2, 3
MODULE_NAMES = {
    MODULE_NONE: "Kein Modul",
    MODULE_BUTTONS: "Zusatztasten",
    MODULE_SLIDERS: "Slider",
    MODULE_KNOBS: "Potis",
}

DATE_FORMATS = {"de": "%d.%m", "zh": "%m-%d", "ja": "%m/%d"}


def date_format(lang: str) -> str:
    return DATE_FORMATS.get(lang, "%d/%m")


@dataclass
class Frame:
    main: list[int]
    enc_click: int
    enc_value: int
    module: int
    extra: list[int] = field(default_factory=list)


def parse_line(line: str) -> Frame | None:
    parts = line.strip().split(";")
    if len(parts) < 12:
        return None
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    return Frame(main=nums[0:9], enc_click=nums[9], enc_value=nums[10], module=nums[11], extra=nums[12:])


@dataclass
class InputEvent:
    kind: str  # press | release | rotate | analog | module
    key: str = ""
    value: float | None = None
    delta: float = 0.0


class InputTracker:
    """Vergleicht aufeinanderfolgende Frames und erzeugt Ereignisse."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._main = [0] * 9
        self._enc_click = 0
        self._enc_value: int | None = None
        self._module: int | None = None
        self._ext = [0] * 6
        self._analog: dict[str, int] = {}

    def feed(self, f: Frame) -> list[InputEvent]:
        events: list[InputEvent] = []

        if f.module != self._module:
            self._module = f.module
            self._ext = [0] * 6
            self._analog.clear()
            events.append(InputEvent("module", value=f.module))

        self._buttons(events, f.main, self._main, "btn")
        if f.enc_click != self._enc_click:
            events.append(InputEvent("press" if f.enc_click else "release", "enc_click"))
            self._enc_click = f.enc_click

        if self._enc_value is not None and f.enc_value != self._enc_value:
            events.append(InputEvent("rotate", "encoder", delta=f.enc_value - self._enc_value))
        self._enc_value = f.enc_value

        if f.module == MODULE_BUTTONS and len(f.extra) >= 6:
            self._buttons(events, f.extra[:6], self._ext, "ext_btn")
        elif f.module in (MODULE_SLIDERS, MODULE_KNOBS) and len(f.extra) >= 2:
            prefix = "slider" if f.module == MODULE_SLIDERS else "knob"
            for i, val in enumerate(f.extra[:2]):
                key = f"{prefix}_{i + 1}"
                if self._analog.get(key) != val:
                    self._analog[key] = val
                    events.append(InputEvent("analog", key, value=float(val)))
        return events

    @staticmethod
    def _buttons(events: list[InputEvent], cur: list[int], prev: list[int], prefix: str) -> None:
        for i, state in enumerate(cur):
            if state != prev[i]:
                events.append(InputEvent("press" if state else "release", f"{prefix}_{i + 1}"))
                prev[i] = state
