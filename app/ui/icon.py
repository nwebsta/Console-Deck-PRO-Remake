"""App-Icon – wird gezeichnet, damit keine Bilddateien nötig sind."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPixmap

ACCENT = QColor("#6c5ce7")


def make_pixmap(size: int = 256, connected: bool = True) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256
    grad = QLinearGradient(0, 0, size, size)
    if connected:
        grad.setColorAt(0, QColor("#8e7bff"))
        grad.setColorAt(1, QColor("#4b3bc4"))
    else:
        grad.setColorAt(0, QColor("#9a9aa5"))
        grad.setColorAt(1, QColor("#5c5c66"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 52 * s, 52 * s)
    p.setBrush(QColor(255, 255, 255, 235))
    cell, gap, start = 52 * s, 18 * s, 41 * s
    for r in range(3):
        for c in range(3):
            p.drawRoundedRect(QRectF(start + c * (cell + gap), start + r * (cell + gap), cell, cell), 12 * s, 12 * s)
    p.end()
    return pm


def app_icon(connected: bool = True) -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_pixmap(size, connected))
    return icon
