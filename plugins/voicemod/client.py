"""Client für die Voicemod Control API (lokaler WebSocket)."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Callable

import websocket

# Voicemod lauscht auf einem dieser Ports (laut Dokumentation der Control API).
PORTS = [59129, 20000, 39273, 42152, 43782, 46667, 35679, 37170, 38501, 33952, 30546]


class VoicemodClient:
    def __init__(self, log: logging.Logger, on_status: Callable[[str], None]):
        self.log = log
        self._on_status = on_status
        self._key = ""
        self._ws: websocket.WebSocket | None = None
        self._send_lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.registered = False
        self.voices: list[dict] = []  # {"id", "name", "favorite", "enabled"}
        self.sounds: list[dict] = []  # {"id", "name"}
        self.current_voice: str | None = None
        self._status = ""

    # ------------------------------------------------------------------ Lebenszyklus
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="voicemod", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        self._close()

    def set_key(self, key: str) -> None:
        key = (key or "").strip()
        if key != self._key:
            self._key = key
            self._close()
            self._wake.set()

    def _status_msg(self, text: str) -> None:
        if text != self._status:
            self._status = text
            self.log.info("Voicemod: %s", text)
            self._on_status(text)

    def _close(self) -> None:
        ws, self._ws = self._ws, None
        self.registered = False
        if ws:
            try:
                ws.close()
            except Exception:
                pass

    def _connect(self) -> websocket.WebSocket | None:
        for port in PORTS:
            if self._stop.is_set():
                return None
            try:
                return websocket.create_connection(f"ws://127.0.0.1:{port}/v1/", timeout=1.0)
            except Exception:
                continue
        return None

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()
            if not self._key:
                self._status_msg("Client-Key fehlt – bitte in den Einstellungen eintragen")
                self._wake.wait(30)
                continue
            ws = self._connect()
            if ws is None:
                self._status_msg("Voicemod nicht gefunden – läuft Voicemod?")
                self._wake.wait(5)
                continue
            self._ws = ws
            self._status_msg("Verbunden, melde an …")
            try:
                self._send_raw("registerClient", {"clientKey": self._key})
                ws.settimeout(1.0)
                while not self._stop.is_set() and self._ws is ws:
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        break
                    try:
                        self._handle(json.loads(raw))
                    except ValueError:
                        continue
            except Exception as exc:
                if self._ws is ws:
                    self.log.debug("Voicemod-Verbindung beendet: %s", exc)
            if self._ws is ws:
                self._close()
            if not self._stop.is_set():
                self._status_msg("Verbindung zu Voicemod verloren – neuer Versuch …")
                self._wake.wait(3)

    # ------------------------------------------------------------------ Senden/Empfangen
    def _send_raw(self, action: str, payload: dict | None = None) -> None:
        ws = self._ws
        if ws is None:
            raise ConnectionError("Voicemod ist nicht verbunden")
        msg = json.dumps({"action": action, "id": str(uuid.uuid4()), "payload": payload or {}})
        with self._send_lock:
            ws.send(msg)

    def send(self, action: str, payload: dict | None = None) -> None:
        if not self.registered:
            raise ConnectionError(f"Voicemod nicht bereit ({self._status or 'nicht verbunden'})")
        self._send_raw(action, payload)

    def refresh_lists(self) -> None:
        self.send("getVoices")
        self.send("getAllSoundboard")
        self.send("getCurrentVoice")

    def _handle(self, msg: dict) -> None:
        action = msg.get("actionType") or msg.get("action") or msg.get("msg") or ""
        payload = msg.get("payload") or msg.get("actionObject") or {}
        if not isinstance(payload, dict):
            payload = {}

        if action == "registerClient":
            status = payload.get("status") or {}
            code = status.get("code", 200) if isinstance(status, dict) else 200
            if code in (200, "200"):
                self.registered = True
                self._status_msg("Verbunden")
                self.refresh_lists()
            else:
                desc = status.get("description", "") if isinstance(status, dict) else ""
                self._status_msg(f"Anmeldung abgelehnt (Code {code}) {desc} – Client-Key prüfen")
        elif action == "getVoices":
            voices = payload.get("voices") or []
            self.voices = [
                {"id": str(v.get("id") or v.get("voiceID")),
                 "name": str(v.get("friendlyName") or v.get("name") or v.get("id")),
                 "favorite": bool(v.get("favorited") or v.get("isFavorite")),
                 "enabled": v.get("enabled", True) is not False}
                for v in voices if isinstance(v, dict) and (v.get("id") or v.get("voiceID"))
            ]
            self.voices.sort(key=lambda v: v["name"].lower())
            if payload.get("currentVoice"):
                self.current_voice = str(payload["currentVoice"])
            self.log.info("Voicemod: %d Stimmen geladen", len(self.voices))
        elif action in ("getCurrentVoice", "voiceLoadedEvent", "loadVoice"):
            vid = payload.get("voiceID") or payload.get("voiceId") or payload.get("id")
            if vid:
                self.current_voice = str(vid)
        elif action == "getAllSoundboard":
            sounds: list[dict] = []
            for board in payload.get("soundboards") or []:
                if not isinstance(board, dict):
                    continue
                bname = board.get("name") or ""
                for s in board.get("sounds") or []:
                    if isinstance(s, dict) and s.get("id"):
                        name = s.get("name") or s["id"]
                        sounds.append({"id": str(s["id"]), "name": f"{bname} › {name}" if bname else name})
            self.sounds = sounds
            self.log.info("Voicemod: %d Sounds geladen", len(sounds))

    # ------------------------------------------------------------------ Komfort
    def cycle_voice(self, step: int, favorites_only: bool) -> None:
        voices = [v for v in self.voices if v["enabled"] and (v["favorite"] or not favorites_only)]
        if not voices:
            raise RuntimeError("Keine (favorisierten) Stimmen verfügbar")
        ids = [v["id"] for v in voices]
        idx = ids.index(self.current_voice) if self.current_voice in ids else -1
        target = ids[(idx + step) % len(ids)]
        self.send("loadVoice", {"voiceID": target})
        self.current_voice = target
