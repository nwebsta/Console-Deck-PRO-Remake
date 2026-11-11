"""Eingebaute Aktionen (entsprechen den Funktionen der bisherigen App + Extras)."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import webbrowser
from pathlib import Path

from . import system
from .base import ActionRegistry, ActionType, Param, RunContext

log = logging.getLogger(__name__)

MEDIA_KEYS = [
    ("playpause", "Play/Pause"),
    ("next", "Nächster Titel"),
    ("prev", "Vorheriger Titel"),
    ("stop", "Stopp"),
]
_MEDIA_VK = {"playpause": 0xB3, "next": 0xB0, "prev": 0xB1, "stop": 0xB2}


def _hotkey_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [p.strip().lower() for p in str(value or "").split("+") if p.strip()]


def register_builtin(registry: ActionRegistry, store, audio: system.AudioPlayer) -> None:
    import pyautogui

    pyautogui.FAILSAFE = False  # Maus in der Ecke darf keine Aktionen abbrechen
    pyautogui.PAUSE = 0.0

    def add(**kw) -> None:
        registry.register(ActionType(**kw))

    # ------------------------------------------------------------------ Starten
    def open_url(m: dict, ctx: RunContext) -> None:
        url = str(m.get("value", "")).strip()
        if url:
            if "://" not in url:
                url = "https://" + url
            webbrowser.open(url)

    def open_app(m: dict, ctx: RunContext) -> None:
        target = os.path.expandvars(str(m.get("value", "")).strip().strip('"'))
        args = str(m.get("args", "") or "").strip()
        if not target:
            return
        path = Path(target)
        if path.suffix.lower() == ".exe" and path.is_file():
            subprocess.Popen(
                [str(path), *shlex.split(args, posix=False)],
                cwd=str(path.parent),
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            )
        elif path.exists():
            os.startfile(str(path), arguments=args) if args else os.startfile(str(path))
        else:
            # Programmname (App Paths, z. B. obs64.exe) oder Protokoll (steam://…)
            os.startfile(target, arguments=args) if args else os.startfile(target)

    add(id="open_url", name="Webseite öffnen", category="Starten", run=open_url,
        params=[Param("value", "URL", "url", help="z. B. https://www.youtube.com")])
    add(id="open_app", name="Programm öffnen", category="Starten", run=open_app,
        params=[Param("value", "Programm / Datei", "app",
                      help="Pfad zur .exe, Verknüpfung, Datei, Ordner oder Programmname (z. B. obs64.exe)"),
                Param("args", "Argumente (optional)", "text")])

    # ------------------------------------------------------------------ Tastatur
    def hotkey(m: dict, ctx: RunContext) -> None:
        keys = _hotkey_list(m.get("value"))
        if len(keys) == 1:
            pyautogui.press(keys[0])
        elif keys:
            pyautogui.hotkey(*keys)

    add(id="hotkey", name="Tastenkombination", category="Tastatur", run=hotkey,
        params=[Param("value", "Tasten", "hotkey")])
    add(id="type", name="Text tippen", category="Tastatur",
        run=lambda m, ctx: system.type_text(str(m.get("value", ""))),
        params=[Param("value", "Text", "multiline")],
        summary=lambda m: "Text: " + str(m.get("value", "")).splitlines()[0][:20] if m.get("value") else "Text tippen")
    add(id="media", name="Mediensteuerung", category="Tastatur",
        run=lambda m, ctx: system._press_vk(_MEDIA_VK.get(m.get("value", "playpause"), 0xB3)),
        params=[Param("value", "Funktion", "choice", default="playpause", choices=MEDIA_KEYS)])

    # ------------------------------------------------------------------ Audio
    def set_volume(m: dict, ctx: RunContext) -> None:
        system.set_volume(ctx.value if ctx.value is not None else float(m.get("value", 50)))

    def change_volume(m: dict, ctx: RunContext) -> None:
        step = float(m.get("value", 2) or 2)
        delta = step * ctx.multiplier
        if abs(delta) < 1:
            delta = 1 if step > 0 else -1
        system.change_volume(delta)

    add(id="set_volume", name="Lautstärke setzen", category="Audio", analog=True, run=set_volume,
        params=[Param("value", "Lautstärke in % (nur Tasten)", "int", default=50, minimum=0, maximum=100,
                      help="Auf Slider/Poti folgt die Lautstärke direkt der Position.")],
        summary=lambda m: "Lautstärke")
    add(id="change_volume", name="Lautstärke ändern", category="Audio", run=change_volume,
        params=[Param("value", "Schritt in % (+/-)", "int", default=2, minimum=-100, maximum=100)],
        summary=lambda m: f"Lautstärke {int(m.get('value', 2)):+d}%")
    add(id="toggle_mute", name="Stummschalten an/aus", category="Audio",
        run=lambda m, ctx: system.toggle_mute())
    add(id="play_audio", name="Sound abspielen", category="Audio",
        run=lambda m, ctx: audio.play(str(m.get("value", ""))) if m.get("value") else None,
        params=[Param("value", "Audiodatei", "file", help="mp3, wav, ogg, …")])
    add(id="stop_audio", name="Alle Sounds stoppen", category="Audio", run=lambda m, ctx: audio.stop_all())

    # ------------------------------------------------------------------ Bildschirm
    def _brightness_now() -> int:
        import screen_brightness_control as sbc

        cur = sbc.get_brightness()
        return int(cur[0] if isinstance(cur, list) else cur)

    def set_brightness(m: dict, ctx: RunContext) -> None:
        import screen_brightness_control as sbc

        if ctx.value is not None:
            sbc.set_brightness(int(max(0, min(100, ctx.value))))
        else:  # Kompatibel zur alten App: auf Tasten ist der Wert eine Änderung
            sbc.set_brightness(max(0, min(100, _brightness_now() + int(m.get("value", 10)))))

    def change_brightness(m: dict, ctx: RunContext) -> None:
        import screen_brightness_control as sbc

        delta = int(m.get("value", 10)) * max(1, round(ctx.multiplier))
        sbc.set_brightness(max(0, min(100, _brightness_now() + delta)))

    add(id="set_brightness", name="Helligkeit (Slider)", category="Bildschirm", analog=True,
        run=set_brightness, threaded=True,
        params=[Param("value", "Änderung in % (nur Tasten)", "int", default=10, minimum=-100, maximum=100,
                      help="Auf Slider/Poti folgt die Helligkeit direkt der Position.")],
        summary=lambda m: "Helligkeit")
    add(id="brightness", name="Helligkeit ändern", category="Bildschirm", run=change_brightness, threaded=True,
        params=[Param("value", "Schritt in % (+/-)", "int", default=10, minimum=-100, maximum=100)],
        summary=lambda m: f"Helligkeit {int(m.get('value', 10)):+d}%")

    # ------------------------------------------------------------------ Home Assistant
    def home_assistant(m: dict, ctx: RunContext) -> None:
        import requests

        ha = store.get("home_assistant", default={}) or {}
        host = str(ha.get("host", "")).rstrip("/")
        token = str(ha.get("token", ""))
        service = str(m.get("service", "")).strip()
        entity = str(m.get("entity_id", "")).strip()
        if not (host and token):
            log.warning("Home Assistant ist nicht eingerichtet (Einstellungen → Home Assistant)")
            return
        if not (service and entity):
            log.warning("Home Assistant: Entität oder Dienst fehlt")
            return
        domain = entity.split(".")[0]
        if "." in service:  # erlaubt z. B. "script.turn_on"
            domain, service = service.split(".", 1)
        resp = requests.post(
            f"{host}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {token}"},
            json={"entity_id": entity},
            timeout=5,
        )
        if resp.status_code == 401:
            log.error("Home Assistant: Token ungültig oder abgelaufen")
        elif resp.status_code >= 400:
            log.error("Home Assistant: HTTP %s – %s", resp.status_code, resp.text[:200])

    add(id="home_assistant", name="Home Assistant", category="Smart Home", run=home_assistant, threaded=True,
        params=[Param("entity_id", "Entität", "text", help="z. B. light.wohnzimmer"),
                Param("service", "Dienst", "choice", default="toggle", choices=[
                    ("toggle", "Umschalten (toggle)"), ("turn_on", "Einschalten (turn_on)"),
                    ("turn_off", "Ausschalten (turn_off)"), ("trigger", "Auslösen (trigger)"),
                    ("media_play_pause", "Play/Pause (Media Player)")])],
        summary=lambda m: f"HA: {m.get('entity_id', '')}")

    # ------------------------------------------------------------------ Profile
    add(id="switch_profile", name="Profil wechseln", category="Profile",
        run=lambda m, ctx: store.set_active_profile(str(m.get("value", ""))),
        params=[Param("value", "Profil", "choice",
                      choices=lambda: [(n, n) for n in store.profile_names()])])
    add(id="next_profile", name="Nächstes Profil", category="Profile",
        run=lambda m, ctx: store.cycle_profile(1))
    add(id="prev_profile", name="Vorheriges Profil", category="Profile",
        run=lambda m, ctx: store.cycle_profile(-1))
