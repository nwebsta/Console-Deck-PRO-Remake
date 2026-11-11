"""PC-Werte (CPU, RAM, GPU) für die Anzeige auf dem Deck."""

from __future__ import annotations

import shutil
import subprocess
import threading
import time

import psutil


class TelemetrySampler:
    def __init__(self, interval: float = 0.5, slow_interval: float = 2.0):
        self._interval = interval
        self._slow_interval = slow_interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._snap = {"cpu": 0, "gpu": -1, "ram": 0, "cpu_freq_mhz": -1, "gpu_temp_c": -1}
        self._nvidia_smi = shutil.which("nvidia-smi")
        self._thread = threading.Thread(target=self._run, name="telemetry", daemon=True)

    def start(self) -> "TelemetrySampler":
        psutil.cpu_percent(interval=None)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._snap)

    def _gpu(self) -> tuple[int, int]:
        if not self._nvidia_smi:
            return -1, -1
        try:
            out = subprocess.run(
                [self._nvidia_smi, "--query-gpu=utilization.gpu,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=1.5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.strip().splitlines()
            load, temp = (int(p.strip()) for p in out[0].split(",")[:2])
            return load, temp
        except Exception:
            return -1, -1

    def _run(self) -> None:
        next_slow = 0.0
        gpu, gpu_temp, freq = -1, -1, -1
        while not self._stop.is_set():
            now = time.monotonic()
            cpu = int(psutil.cpu_percent(interval=None))
            ram = int(psutil.virtual_memory().percent)
            if now >= next_slow:
                gpu, gpu_temp = self._gpu()
                try:
                    f = psutil.cpu_freq()
                    freq = int(f.current) if f and f.current else -1
                except Exception:
                    freq = -1
                next_slow = now + self._slow_interval
            with self._lock:
                self._snap.update(cpu=cpu, gpu=gpu, ram=ram, cpu_freq_mhz=freq, gpu_temp_c=gpu_temp)
            self._stop.wait(self._interval)
