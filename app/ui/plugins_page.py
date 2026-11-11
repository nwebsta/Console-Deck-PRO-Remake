"""Seite „Module“: installieren, aktivieren, einrichten."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..paths import PLUGINS_DIR
from ..plugins import PluginError, PluginManager
from .widgets import ParamForm


class PluginsPage(QWidget):
    def __init__(self, manager: PluginManager) -> None:
        super().__init__()
        self.manager = manager
        self.form: ParamForm | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        head = QHBoxLayout()
        title = QLabel("Module")
        title.setProperty("h2", True)
        head.addWidget(title)
        head.addStretch(1)
        install = QPushButton("Modul installieren (ZIP) …")
        install.setProperty("primary", True)
        install.clicked.connect(self._install)
        folder = QPushButton("Modulordner öffnen")
        folder.clicked.connect(lambda: os.startfile(PLUGINS_DIR))
        reload_btn = QPushButton("Ordner neu einlesen")
        reload_btn.clicked.connect(self.manager.load_all)
        for b in (reload_btn, folder, install):
            head.addWidget(b)
        root.addLayout(head)

        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setFixedWidth(260)
        self.list.currentItemChanged.connect(lambda *_: self._show())
        body.addWidget(self.list)

        detail = QWidget()
        self.detail = QVBoxLayout(detail)
        self.detail.setContentsMargins(16, 0, 0, 0)
        self.name = QLabel()
        self.name.setProperty("h2", True)
        self.meta = QLabel()
        self.meta.setProperty("hint", True)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.actions_label = QLabel()
        self.actions_label.setWordWrap(True)
        self.actions_label.setProperty("hint", True)
        for w in (self.name, self.meta, self.desc, self.status, self.actions_label):
            self.detail.addWidget(w)
        self.settings_title = QLabel("Einstellungen")
        self.settings_title.setProperty("h3", True)
        self.detail.addWidget(self.settings_title)
        self.form_host = QVBoxLayout()
        self.detail.addLayout(self.form_host)
        self.save_btn = QPushButton("Einstellungen speichern")
        self.save_btn.clicked.connect(self._save_settings)
        self.detail.addWidget(self.save_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.detail.addStretch(1)
        btns = QHBoxLayout()
        self.toggle_btn = QPushButton()
        self.toggle_btn.clicked.connect(self._toggle)
        self.remove_btn = QPushButton("Entfernen")
        self.remove_btn.clicked.connect(self._remove)
        btns.addWidget(self.toggle_btn)
        btns.addWidget(self.remove_btn)
        btns.addStretch(1)
        self.detail.addLayout(btns)
        body.addWidget(detail, 1)
        root.addLayout(body, 1)

        self.empty = QLabel("Noch keine Module installiert.\nModule gibt es als ZIP-Datei – "
                            "z. B. das Voicemod-Modul aus den Releases.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setProperty("hint", True)
        root.addWidget(self.empty)

        manager.plugins_changed.connect(self.refresh)
        manager.status_changed.connect(self._on_status)
        self.refresh()

    def _selected_id(self) -> str | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def refresh(self) -> None:
        keep = self._selected_id()
        self.list.blockSignals(True)
        self.list.clear()
        for info in sorted(self.manager.plugins.values(), key=lambda i: i.name.lower()):
            state = "●" if info.loaded else ("⚠" if info.error else "○")
            item = QListWidgetItem(f"{state}  {info.name}   {info.version}")
            item.setData(Qt.ItemDataRole.UserRole, info.id)
            self.list.addItem(item)
            if info.id == keep:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        has = self.list.count() > 0
        self.empty.setVisible(not has)
        self.list.parentWidget().setVisible(True)
        self._show()

    def _on_status(self, plugin_id: str) -> None:
        if plugin_id == self._selected_id():
            self._show_status(self.manager.plugins.get(plugin_id))

    def _show_status(self, info) -> None:
        if info is None:
            return
        if info.error:
            self.status.setText(f"⚠ Fehler: {info.error}")
        elif not info.loaded:
            self.status.setText("Deaktiviert")
        else:
            self.status.setText(f"Status: {info.status or 'aktiv'}")

    def _show(self) -> None:
        info = self.manager.plugins.get(self._selected_id() or "")
        widgets = (self.name, self.meta, self.desc, self.status, self.actions_label,
                   self.toggle_btn, self.remove_btn, self.settings_title, self.save_btn)
        for w in widgets:
            w.setVisible(info is not None)
        if self.form:
            self.form.setParent(None)
            self.form.deleteLater()
            self.form = None
        if info is None:
            return
        self.name.setText(info.name)
        meta = f"Version {info.version}"
        if info.author:
            meta += f" · von {info.author}"
        if info.dev:
            meta += " · aus Projektordner (Entwicklung)"
        self.meta.setText(meta)
        self.desc.setText(info.description)
        self._show_status(info)
        actions = [a.name for a in self.manager.registry.all() if a.source == info.id]
        self.actions_label.setText("Aktionen: " + ", ".join(actions) if actions else "")
        self.toggle_btn.setText("Deaktivieren" if info.loaded else "Aktivieren")
        self.remove_btn.setEnabled(not info.dev)
        has_settings = info.loaded and bool(info.settings_params)
        self.settings_title.setVisible(has_settings)
        self.save_btn.setVisible(has_settings)
        if has_settings and info.api:
            self.form = ParamForm(info.settings_params, info.api.settings)
            self.form_host.addWidget(self.form)

    def _save_settings(self) -> None:
        info = self.manager.plugins.get(self._selected_id() or "")
        if info and info.api and self.form:
            info.api.save_settings(self.form.values())

    def _toggle(self) -> None:
        info = self.manager.plugins.get(self._selected_id() or "")
        if info:
            self.manager.set_enabled(info.id, not info.loaded)

    def _remove(self) -> None:
        info = self.manager.plugins.get(self._selected_id() or "")
        if not info:
            return
        if QMessageBox.question(self, "Modul entfernen",
                                f"Modul „{info.name}“ entfernen? Belegungen mit seinen Aktionen bleiben "
                                "erhalten, funktionieren aber erst nach erneuter Installation.") \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            self.manager.remove(info.id)
        except PluginError as exc:
            QMessageBox.warning(self, "Modul entfernen", str(exc))

    def _install(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Modul installieren", "", "Modul (*.zip)")
        if not path:
            return
        try:
            info = self.manager.install_zip(path)
        except PluginError as exc:
            QMessageBox.warning(self, "Modul installieren", str(exc))
            return
        if info.error:
            QMessageBox.warning(self, "Modul installieren",
                                f"„{info.name}“ wurde installiert, konnte aber nicht geladen werden:\n{info.error}")
        else:
            QMessageBox.information(self, "Modul installieren", f"„{info.name}“ {info.version} ist installiert.")
