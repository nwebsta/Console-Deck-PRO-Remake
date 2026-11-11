"""Seite „Deck“: Profile verwalten und Tasten/Regler belegen."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..device.protocol import MODULE_NAMES, InputEvent
from ..engine import INPUT_GROUPS
from ..focus_watcher import foreground_exe
from .action_dialog import ActionDialog

COLUMNS = {"main": 3, "encoder": 3, "ext": 3, "sliders": 3, "knobs": 3}


class InputButton(QPushButton):
    def __init__(self, key: str, label: str, big: bool) -> None:
        super().__init__()
        self.key = key
        self.label = label
        self.setProperty("deckButton", True)
        self.setProperty("big", big)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumSize(96, 86 if big else 64)
        self._timer = QTimer(self, singleShot=True, interval=180)
        self._timer.timeout.connect(lambda: self._set_active(False))

    def set_summary(self, text: str) -> None:
        self.setProperty("assigned", bool(text))
        self.setText(f"{self.label}\n{text or '—'}")
        self.setToolTip(text or "Nicht belegt")
        self._repolish()

    def flash(self, hold: bool | None = None) -> None:
        if hold is None:
            self._set_active(True)
            self._timer.start()
        else:
            self._set_active(hold)

    def _set_active(self, on: bool) -> None:
        self.setProperty("active", on)
        self._repolish()

    def _repolish(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)


class ProfileAppsDialog(QDialog):
    def __init__(self, parent: QWidget, name: str, apps: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Automatischer Wechsel – {name}")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        info = QLabel(
            "Dieses Profil wird automatisch aktiv, solange eines dieser Programme im Vordergrund ist. "
            "Ein Programmname (z. B. <b>obs64.exe</b>) pro Zeile.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.edit = QPlainTextEdit("\n".join(apps))
        lay.addWidget(self.edit)
        pick = QPushButton("Programm im Vordergrund übernehmen (in 3 s)")
        pick.clicked.connect(self._pick)
        lay.addWidget(pick)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _pick(self) -> None:
        def grab():
            exe = foreground_exe()
            if exe and exe not in self.apps():
                self.edit.appendPlainText(exe)
            self.raise_()
            self.activateWindow()
        QTimer.singleShot(3000, grab)

    def apps(self) -> list[str]:
        return [a.strip() for a in self.edit.toPlainText().splitlines() if a.strip()]


class DeckPage(QWidget):
    def __init__(self, store, registry, engine) -> None:
        super().__init__()
        self.store = store
        self.registry = registry
        self.engine = engine
        self.buttons: dict[str, InputButton] = {}
        self.groups: dict[str, QGroupBox] = {}
        self.group_titles: dict[str, str] = {}
        self.analog_values: dict[str, float] = {}
        self.current_module: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)

        # ---------------------------------------------------- Profilleiste
        bar = QHBoxLayout()
        title = QLabel("Profil")
        title.setProperty("h2", True)
        bar.addWidget(title)
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(200)
        self.profile_combo.activated.connect(self._on_profile_selected)
        bar.addWidget(self.profile_combo)
        self.auto_label = QLabel()
        self.auto_label.setProperty("hint", True)
        bar.addWidget(self.auto_label)
        bar.addStretch(1)
        for text, slot in (("Neu", self._new), ("Duplizieren", self._duplicate), ("Umbenennen", self._rename),
                           ("Auto-Wechsel …", self._apps), ("Löschen", self._delete)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            bar.addWidget(b)
        root.addLayout(bar)

        # ---------------------------------------------------- Eingaben
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 8, 0, 0)
        grid.setSpacing(14)
        positions = {"main": (0, 0, 2, 1), "encoder": (2, 0, 1, 1), "ext": (0, 1, 1, 1),
                     "sliders": (1, 1, 1, 1), "knobs": (2, 1, 1, 1)}
        for gid, gtitle, _module, items in INPUT_GROUPS:
            box = QGroupBox(gtitle)
            self.groups[gid] = box
            self.group_titles[gid] = gtitle
            g = QGridLayout(box)
            g.setSpacing(8)
            cols = COLUMNS[gid]
            for i, (key, label) in enumerate(items):
                btn = InputButton(key, label, big=gid == "main")
                btn.clicked.connect(lambda _=False, k=key: self._edit(k))
                self.buttons[key] = btn
                g.addWidget(btn, i // cols, i % cols)
            for c in range(cols):
                g.setColumnStretch(c, 1)
            r, c, rs, cs = positions[gid]
            grid.addWidget(box, r, c, rs, cs, Qt.AlignmentFlag.AlignTop)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(3, 1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        store.profiles_changed.connect(self.refresh)
        store.active_profile_changed.connect(lambda *_: self.refresh())
        store.changed.connect(self._refresh_summaries)
        registry.listeners.append(lambda: QTimer.singleShot(0, self, self._refresh_summaries))
        engine.input_event.connect(self._on_input)
        self.refresh()

    # ---------------------------------------------------- Anzeige
    def refresh(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(self.store.profile_names())
        self.profile_combo.setCurrentText(self.store.current_profile)
        self.profile_combo.blockSignals(False)
        self.auto_label.setText("automatisch gewählt" if self.store.is_auto_profile else "")
        self._refresh_summaries()

    def _refresh_summaries(self) -> None:
        for key, btn in self.buttons.items():
            btn.set_summary(self.registry.describe(self.store.mapping(key)))

    def _update_group_titles(self) -> None:
        for gid, _t, module, _items in INPUT_GROUPS:
            title = self.group_titles[gid]
            if module is not None and module == self.current_module:
                title += "  ●  angeschlossen"
                if gid in ("sliders", "knobs"):
                    prefix = "slider" if gid == "sliders" else "knob"
                    vals = [self.analog_values.get(f"{prefix}_{i}") for i in (1, 2)]
                    if all(v is not None for v in vals):
                        title += f"  ({vals[0]:.0f} % / {vals[1]:.0f} %)"
            self.groups[gid].setTitle(title)

    def _on_input(self, ev: InputEvent) -> None:
        if ev.kind in ("press", "release") and ev.key in self.buttons:
            self.buttons[ev.key].flash(ev.kind == "press")
        elif ev.kind == "rotate":
            btn = self.buttons["enc_cw" if ev.delta > 0 else "enc_ccw"]
            btn.flash()
        elif ev.kind == "analog":
            self.analog_values[ev.key] = ev.value or 0.0
            if ev.key in self.buttons:
                self.buttons[ev.key].flash()
            self._update_group_titles()
        elif ev.kind == "module":
            self.current_module = int(ev.value or 0)
            self.analog_values.clear()
            self._update_group_titles()

    def set_disconnected(self) -> None:
        self.current_module = None
        self._update_group_titles()

    @property
    def module_name(self) -> str:
        return MODULE_NAMES.get(self.current_module or 0, "Unbekannt")

    # ---------------------------------------------------- Aktionen
    def _edit(self, key: str) -> None:
        dlg = ActionDialog(self, key, self.store.mapping(key), self.registry, self.engine)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.store.set_mapping(key, dlg.result_mapping)

    def _on_profile_selected(self) -> None:
        self.store.set_active_profile(self.profile_combo.currentText())

    def _ask_name(self, title: str, default: str = "") -> str | None:
        name, ok = QInputDialog.getText(self, title, "Name des Profils:", text=default)
        name = name.strip()
        if not ok or not name:
            return None
        if name in self.store.profile_names() and name != default:
            QMessageBox.warning(self, title, f"Ein Profil „{name}“ gibt es bereits.")
            return None
        return name

    def _new(self) -> None:
        name = self._ask_name("Neues Profil")
        if name and self.store.add_profile(name):
            self.store.set_active_profile(name)

    def _duplicate(self) -> None:
        src = self.store.current_profile
        name = self._ask_name("Profil duplizieren", f"{src} (Kopie)")
        if name and self.store.add_profile(name, copy_from=src):
            self.store.set_active_profile(name)

    def _rename(self) -> None:
        old = self.store.current_profile
        name = self._ask_name("Profil umbenennen", old)
        if name and name != old:
            self.store.rename_profile(old, name)

    def _delete(self) -> None:
        name = self.store.current_profile
        if len(self.store.profile_names()) <= 1:
            QMessageBox.information(self, "Profil löschen", "Das letzte Profil kann nicht gelöscht werden.")
            return
        if QMessageBox.question(self, "Profil löschen", f"Profil „{name}“ wirklich löschen?") \
                == QMessageBox.StandardButton.Yes:
            self.store.delete_profile(name)

    def _apps(self) -> None:
        name = self.store.current_profile
        prof = self.store.profile(name) or {}
        dlg = ProfileAppsDialog(self, name, prof.get("apps", []))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.store.set_profile_apps(name, dlg.apps())
