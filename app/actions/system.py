"""Windows-Systemfunktionen: Lautstärke, Tastatur, Audio-Wiedergabe."""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

from PySide6.QtCore import QObject, QUrl, Signal, Slot

log = logging.getLogger(__name__)
IS_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------------------- Lautstärke


def _endpoint():
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


def _press_vk(vk: int, count: int = 1) -> None:
    for _ in range(max(1, count)):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 0x0002, 0)


VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF


def get_volume() -> int:
    return round(_endpoint().GetMasterVolumeLevelScalar() * 100)


def set_volume(percent: float) -> None:
    percent = max(0.0, min(100.0, float(percent)))
    try:
        _endpoint().SetMasterVolumeLevelScalar(percent / 100.0, None)
    except Exception as exc:
        log.debug("pycaw nicht verfügbar (%s) – nutze Lautstärketasten", exc)
        # Grobe Annäherung: Windows ändert pro Tastendruck um 2 %.
        _press_vk(VK_VOLUME_DOWN, 50)
        _press_vk(VK_VOLUME_UP, round(percent / 2))


def change_volume(delta: float) -> None:
    try:
        ep = _endpoint()
        cur = ep.GetMasterVolumeLevelScalar() * 100
        ep.SetMasterVolumeLevelScalar(max(0.0, min(100.0, cur + delta)) / 100.0, None)
        if delta > 0 and ep.GetMute():
            ep.SetMute(0, None)
    except Exception as exc:
        log.debug("pycaw nicht verfügbar (%s) – nutze Lautstärketasten", exc)
        _press_vk(VK_VOLUME_UP if delta > 0 else VK_VOLUME_DOWN, max(1, round(abs(delta) / 2)))


def toggle_mute() -> None:
    try:
        ep = _endpoint()
        ep.SetMute(0 if ep.GetMute() else 1, None)
    except Exception:
        _press_vk(VK_VOLUME_MUTE)


# ---------------------------------------------------------------------------- Text tippen

ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_VK_RETURN = 0x0D


def _key(vk: int = 0, scan: int = 0, flags: int = 0) -> _INPUT:
    inp = _INPUT(type=_INPUT_KEYBOARD)
    inp.u.ki = _KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return inp


def type_text(text: str) -> None:
    """Tippt beliebigen Unicode-Text (inkl. Umlaute/Emoji) in das aktive Fenster."""
    if not IS_WINDOWS:
        import pyautogui

        pyautogui.write(text)
        return
    inputs: list[_INPUT] = []
    for ch in text.replace("\r\n", "\n"):
        if ch == "\n":
            inputs += [_key(vk=_VK_RETURN), _key(vk=_VK_RETURN, flags=_KEYEVENTF_KEYUP)]
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i : i + 2], "little")
            inputs += [
                _key(scan=unit, flags=_KEYEVENTF_UNICODE),
                _key(scan=unit, flags=_KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP),
            ]
    if inputs:
        arr = (_INPUT * len(inputs))(*inputs)
        ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


# ---------------------------------------------------------------------------- Audio


class AudioPlayer(QObject):
    """Spielt Audiodateien über QtMultimedia im GUI-Thread ab (mp3, wav, ogg, …)."""

    _play = Signal(str)
    _stop = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._players: list = []
        self._play.connect(self._on_play)
        self._stop.connect(self._on_stop)

    def play(self, path: str) -> None:
        self._play.emit(path)

    def stop_all(self) -> None:
        self._stop.emit()

    @Slot(str)
    def _on_play(self, path: str) -> None:
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        player = QMediaPlayer(self)
        output = QAudioOutput(player)
        output.setVolume(1.0)
        player.setAudioOutput(output)

        def on_status(status):
            if status in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
                if status == QMediaPlayer.MediaStatus.InvalidMedia:
                    log.error("Audiodatei kann nicht abgespielt werden: %s", path)
                self._discard(player)

        player.mediaStatusChanged.connect(on_status)
        player.setSource(QUrl.fromLocalFile(path))
        player.play()
        self._players.append(player)

    def _discard(self, player) -> None:
        if player in self._players:
            self._players.remove(player)
            player.stop()
            player.deleteLater()

    @Slot()
    def _on_stop(self) -> None:
        for p in list(self._players):
            self._discard(p)
