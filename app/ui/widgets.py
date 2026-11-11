"""Wiederverwendbare Eingabe-Widgets."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QWidget,
)

from ..actions.base import Param

K = Qt.Key
_KEY_NAMES = {
    K.Key_Return: "enter", K.Key_Enter: "enter", K.Key_Escape: "esc", K.Key_Tab: "tab",
    K.Key_Backspace: "backspace", K.Key_Delete: "delete", K.Key_Insert: "insert",
    K.Key_Home: "home", K.Key_End: "end", K.Key_PageUp: "pageup", K.Key_PageDown: "pagedown",
    K.Key_Left: "left", K.Key_Right: "right", K.Key_Up: "up", K.Key_Down: "down",
    K.Key_Space: "space", K.Key_Print: "printscreen", K.Key_Pause: "pause",
    K.Key_CapsLock: "capslock", K.Key_NumLock: "numlock", K.Key_ScrollLock: "scrolllock",
    K.Key_VolumeUp: "volumeup", K.Key_VolumeDown: "volumedown", K.Key_VolumeMute: "volumemute",
    K.Key_MediaPlay: "playpause", K.Key_MediaTogglePlayPause: "playpause",
    K.Key_MediaNext: "nexttrack", K.Key_MediaPrevious: "prevtrack", K.Key_MediaStop: "stop",
    K.Key_Menu: "apps",
}
_MODIFIER_KEYS = {K.Key_Control, K.Key_Shift, K.Key_Alt, K.Key_Meta, K.Key_AltGr}


def key_name(event: QKeyEvent) -> str | None:
    key = event.key()
    if key in _KEY_NAMES:
        return _KEY_NAMES[key]
    if K.Key_F1.value <= key <= K.Key_F24.value:
        return f"f{key - K.Key_F1.value + 1}"
    vk = event.nativeVirtualKey()
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:  # Ziffern/Buchstaben unabhängig von Shift
        return chr(vk).lower()
    if 0x60 <= vk <= 0x69:
        return f"num{vk - 0x60}"
    text = event.text()
    if text and text.isprintable() and not text.isspace():
        return text.lower()
    return None


class HotkeyLineEdit(QLineEdit):
    recorded = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.recording = False

    def start(self) -> None:
        self.recording = True
        self.setPlaceholderText("Tastenkombination drücken …")
        self.clear()
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.recording:
            return super().keyPressEvent(event)
        if event.key() in _MODIFIER_KEYS:
            return
        mods = event.modifiers()
        keys = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            keys.append("ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            keys.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            keys.append("shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            keys.append("win")
        name = key_name(event)
        if name:
            keys.append(name)
            self.recording = False
            self.setPlaceholderText("z. B. ctrl+shift+m")
            self.setText("+".join(keys))
            self.recorded.emit(keys)

    def focusOutEvent(self, event) -> None:
        self.recording = False
        super().focusOutEvent(event)


class HotkeyEdit(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = HotkeyLineEdit()
        self.edit.setPlaceholderText("z. B. ctrl+shift+m")
        btn = QPushButton("Aufnehmen")
        btn.clicked.connect(self.edit.start)
        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)

    def value(self) -> list[str]:
        return [p.strip().lower() for p in self.edit.text().split("+") if p.strip()]

    def set_value(self, value: Any) -> None:
        if isinstance(value, list):
            value = "+".join(str(v) for v in value)
        self.edit.setText(str(value or ""))


class PathEdit(QWidget):
    def __init__(self, kind: str) -> None:
        super().__init__()
        self.kind = kind
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        btn = QToolButton()
        btn.setText("…")
        btn.clicked.connect(self._browse)
        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)

    def _browse(self) -> None:
        if self.kind == "app":
            flt = "Programme und Verknüpfungen (*.exe *.lnk *.bat *.cmd *.url);;Alle Dateien (*)"
        else:
            flt = "Audio (*.mp3 *.wav *.ogg *.flac *.m4a);;Alle Dateien (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Datei wählen", self.edit.text(), flt)
        if path:
            self.edit.setText(path.replace("/", "\\"))


class ChoiceEdit(QWidget):
    def __init__(self, param: Param) -> None:
        super().__init__()
        self.param = param
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox()
        self.combo.setMinimumWidth(220)
        lay.addWidget(self.combo, 1)
        if callable(param.choices):
            btn = QToolButton()
            btn.setText("⟳")
            btn.setToolTip("Liste aktualisieren")
            btn.clicked.connect(lambda: self.reload(self.value()))
            lay.addWidget(btn)
        self.reload(param.default)

    def reload(self, keep: Any = None) -> None:
        self.combo.clear()
        for value, label in self.param.get_choices():
            self.combo.addItem(label, value)
        self.set_value(keep)

    def value(self) -> Any:
        return self.combo.currentData()

    def set_value(self, value: Any) -> None:
        if value in (None, ""):
            return
        idx = self.combo.findData(value)
        if idx < 0:
            self.combo.addItem(f"{value} (nicht verfügbar)", value)
            idx = self.combo.count() - 1
        self.combo.setCurrentIndex(idx)


class ParamForm(QWidget):
    """Erzeugt ein Formular aus einer Liste von Param-Definitionen."""

    def __init__(self, params: list[Param], values: dict | None = None) -> None:
        super().__init__()
        self.params = params
        self.fields: dict[str, QWidget] = {}
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        for p in params:
            w = self._make(p)
            self.fields[p.key] = w
            form.addRow(p.label, w)
            if p.help:
                hint = QLabel(p.help)
                hint.setWordWrap(True)
                hint.setProperty("hint", True)
                form.addRow("", hint)
        self.set_values({p.key: p.default for p in params if p.default is not None})
        if values:
            self.set_values(values)

    @staticmethod
    def _make(p: Param) -> QWidget:
        if p.kind == "int":
            w = QSpinBox()
            w.setRange(p.minimum, p.maximum)
            return w
        if p.kind == "bool":
            return QCheckBox()
        if p.kind == "multiline":
            w = QPlainTextEdit()
            w.setFixedHeight(90)
            return w
        if p.kind in ("file", "app"):
            return PathEdit(p.kind)
        if p.kind == "hotkey":
            return HotkeyEdit()
        if p.kind == "choice":
            return ChoiceEdit(p)
        w = QLineEdit()
        if p.kind == "password":
            w.setEchoMode(QLineEdit.EchoMode.Password)
        return w

    def set_values(self, values: dict) -> None:
        for p in self.params:
            if p.key not in values:
                continue
            w, v = self.fields[p.key], values[p.key]
            if isinstance(w, QSpinBox):
                try:
                    w.setValue(int(float(v)))
                except (TypeError, ValueError):
                    pass
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(v))
            elif isinstance(w, QPlainTextEdit):
                w.setPlainText(str(v or ""))
            elif isinstance(w, PathEdit):
                w.edit.setText(str(v or ""))
            elif isinstance(w, (HotkeyEdit, ChoiceEdit)):
                w.set_value(v)
            elif isinstance(w, QLineEdit):
                w.setText(str(v or ""))

    def values(self) -> dict:
        out: dict = {}
        for p in self.params:
            w = self.fields[p.key]
            if isinstance(w, QSpinBox):
                out[p.key] = w.value()
            elif isinstance(w, QCheckBox):
                out[p.key] = w.isChecked()
            elif isinstance(w, QPlainTextEdit):
                out[p.key] = w.toPlainText()
            elif isinstance(w, PathEdit):
                out[p.key] = w.edit.text().strip()
            elif isinstance(w, (HotkeyEdit, ChoiceEdit)):
                out[p.key] = w.value()
            elif isinstance(w, QLineEdit):
                out[p.key] = w.text().strip()
        return out
