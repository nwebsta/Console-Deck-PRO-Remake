"""Dialog zum Belegen einer Taste / eines Reglers."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..actions.base import ActionRegistry
from ..engine import ANALOG_INPUTS, INPUT_LABELS
from .widgets import ParamForm

NONE_ID = ""


class ActionDialog(QDialog):
    def __init__(self, parent: QWidget | None, input_key: str, mapping: dict | None,
                 registry: ActionRegistry, engine) -> None:
        super().__init__(parent)
        self.registry = registry
        self.engine = engine
        self.analog_only = input_key in ANALOG_INPUTS
        self.mapping = dict(mapping or {})
        self.result_mapping: dict | None = None
        self.form: ParamForm | None = None

        self.setWindowTitle(f"Belegung – {INPUT_LABELS.get(input_key, input_key)}")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)

        top = QFormLayout()
        self.combo = QComboBox()
        self.combo.setMaxVisibleItems(25)
        top.addRow("Aktion", self.combo)
        lay.addLayout(top)

        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setProperty("hint", True)
        lay.addWidget(self.desc)
        if self.analog_only:
            note = QLabel("Für die Position eines Slider/Potis sind nur Aktionen verfügbar, die einen Wert "
                          "von 0–100 % verstehen. Für einfache Aktionen „hoch/runter“ belegen.")
            note.setWordWrap(True)
            note.setProperty("hint", True)
            lay.addWidget(note)

        self.form_host = QVBoxLayout()
        lay.addLayout(self.form_host)
        lay.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.test_btn = QPushButton("Testen")
        self.test_btn.setToolTip("Aktion jetzt einmal ausführen")
        buttons.addButton(self.test_btn, QDialogButtonBox.ButtonRole.ActionRole)
        self.test_btn.clicked.connect(self._test)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self._fill_combo()
        idx = self.combo.findData(self.mapping.get("action", NONE_ID))
        if idx < 0 and self.mapping.get("action"):
            self.combo.addItem(f"⚠ {self.mapping['action']} (Modul fehlt)", self.mapping["action"])
            idx = self.combo.count() - 1
        self.combo.currentIndexChanged.connect(self._on_change)
        self.combo.setCurrentIndex(max(idx, 0))
        self._on_change()

    def _fill_combo(self) -> None:
        self.combo.addItem("— Keine Aktion —", NONE_ID)
        model: QStandardItemModel = self.combo.model()
        category = None
        for at in self.registry.all():
            if self.analog_only and not at.analog:
                continue
            if at.category != category:
                category = at.category
                self.combo.addItem(category, None)
                item = model.item(self.combo.count() - 1)
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.combo.addItem("    " + at.name, at.id)

    def _on_change(self) -> None:
        if self.form:
            self.form.setParent(None)
            self.form.deleteLater()
            self.form = None
        at = self.registry.get(self.combo.currentData())
        self.test_btn.setEnabled(at is not None)
        self.desc.setText(at.description if at else "")
        self.desc.setVisible(bool(at and at.description))
        if at and at.params:
            values = self.mapping if self.mapping.get("action") == at.id else {}
            self.form = ParamForm(at.params, values)
            self.form_host.addWidget(self.form)

    def _current(self) -> dict | None:
        action = self.combo.currentData()
        if not action:
            return None
        mapping = {"action": action}
        if self.form:
            mapping.update(self.form.values())
        elif self.mapping.get("action") == action:
            mapping = dict(self.mapping)  # Modul fehlt: Belegung unverändert lassen
        return mapping

    def _test(self) -> None:
        mapping = self._current()
        if mapping:
            self.engine.test(mapping)

    def _save(self) -> None:
        self.result_mapping = self._current()
        self.accept()
