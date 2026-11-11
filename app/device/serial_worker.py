"""Verbindung zum Deck über die serielle Schnittstelle."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import serial
from PySide6.QtCore import QObject, Signal
from serial.tools import list_ports

from .protocol import InputTracker, date_format, parse_line
from .telemetry import TelemetrySampler

log = logging.getLogger(__name__)

STATS_INTERVAL = 0.5


def available_ports() -> list[tuple[str, str]]:
    return [(p.device, p.description or p.device) for p in sorted(list_ports.comports(), key=lambda p: p.device)]


class SerialWorker(QObject):
    # Zustand: no_port | connecting | connected | error
    status_changed = Signal(str, str)

    def __init__(self, store, engine):
        super().__init__()
        self._store = store
        self._engine = engine
        self._telemetry = TelemetrySampler().start()
        self._tracker = InputTracker()
        self._stop = threading.Event()
        self._reconnect = threading.Event()
        self._thread = threading.Thread(target=self._run, name="serial", daemon=True)
        self.state = "no_port"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._reconnect.set()
        self._telemetry.stop()
        self._thread.join(timeout=2)

    def reconnect(self) -> None:
        """Nach Änderung von Port/Baudrate neu verbinden."""
        self._reconnect.set()

    def _status(self, state: str, msg: str) -> None:
        if state != self.state or state == "error":
            log.info(msg)
        self.state = state
        self.status_changed.emit(state, msg)

    def _wait(self, seconds: float) -> None:
        self._reconnect.wait(seconds)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._reconnect.clear()
            port = self._store.get("serial", "port")
            baud = int(self._store.get("serial", "baud_rate", default=115200) or 115200)
            if not port:
                self._status("no_port", "Kein COM-Port gewählt (Einstellungen → Verbindung)")
                self._wait(2)
                continue
            self._status("connecting", f"Verbinde mit {port} …")
            try:
                ser = serial.Serial(port, baud, timeout=0.02)
            except (serial.SerialException, OSError) as exc:
                hint = " – Port wird evtl. von einem anderen Programm benutzt" if "denied" in str(exc).lower() or "zugriff" in str(exc).lower() else ""
                self._status("error", f"{port} nicht verfügbar{hint}")
                self._wait(5)
                continue
            try:
                self._session(ser, port)
            except (serial.SerialException, OSError) as exc:
                self._status("error", f"Verbindung zu {port} getrennt ({exc})")
                self._wait(3)
            finally:
                try:
                    ser.close()
                except Exception:
                    pass
        self.status_changed.emit("no_port", "Beendet")

    def _session(self, ser: serial.Serial, port: str) -> None:
        # Der Arduino startet beim Öffnen des Ports neu.
        if self._reconnect.wait(2) or self._stop.is_set():
            return
        ser.reset_input_buffer()
        self._tracker.reset()
        self._status("connected", f"Verbunden mit {port}")
        self._send_boot(ser)

        buf = b""
        next_stats = time.monotonic()
        while not self._stop.is_set() and not self._reconnect.is_set():
            chunk = ser.read(ser.in_waiting or 1)
            if chunk:
                buf += chunk
                *lines, buf = buf.split(b"\n")
                if len(buf) > 512:
                    buf = b""
                for raw in lines:
                    frame = parse_line(raw.decode("utf-8", errors="ignore"))
                    if frame:
                        for ev in self._tracker.feed(frame):
                            self._engine.handle(ev)
            now = time.monotonic()
            if now >= next_stats:
                self._send_stats(ser)
                next_stats = now + STATS_INTERVAL

    def _dates(self) -> tuple[str, str]:
        now = datetime.now()
        return now.strftime("%H:%M:%S"), now.strftime(date_format(self._store.get("language", default="de")))

    def _send_boot(self, ser: serial.Serial) -> None:
        t, d = self._dates()
        ser.write(f"BOOT:{t},{d}\n".encode())

    def _send_stats(self, ser: serial.Serial) -> None:
        s = self._telemetry.snapshot()
        t, d = self._dates()
        ser.write(
            f"STATS:{s['cpu']},{s['gpu']},{s['ram']},{s['cpu_freq_mhz']},{s['gpu_temp_c']},{t},{d}\n".encode()
        )
