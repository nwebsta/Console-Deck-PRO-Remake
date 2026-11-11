# Eigene Module entwickeln

Ein Modul erweitert die App um neue Aktionen, die man auf Tasten und Regler legen kann. Das Voicemod-Modul in [`plugins/voicemod`](../plugins/voicemod) ist ein vollständiges Beispiel.

## Aufbau

```
mein_modul/
├── plugin.json      # Beschreibung
├── __init__.py      # Einstieg mit register(api)
├── …                # weitere .py-Dateien (relativ importierbar: from .client import X)
└── lib/             # optional: mitgelieferte reine Python-Bibliotheken
```

### plugin.json

```json
{
    "id": "mein_modul",
    "name": "Mein Modul",
    "version": "1.0.0",
    "author": "Dein Name",
    "description": "Was das Modul macht.",
    "api_version": 1,
    "entry": "__init__.py"
}
```

`id` darf nur `a-z`, `0-9`, `_` und `-` enthalten. Gespeicherte Belegungen verweisen auf `<id>.<aktion>`, deshalb sollte sich die ID nie ändern.

### \_\_init\_\_.py

```python
from app.plugin_api import Param


def register(api):
    api.register_settings([Param("token", "API-Token", "password")])

    def say_hello(mapping, ctx):
        api.log.info("Hallo %s (Taste: %s)", mapping.get("name"), ctx.input_key)

    api.register_action(
        "hello", "Hallo sagen", say_hello,
        [Param("name", "Name", "text", default="Welt")],
    )
```

## API (`api`)

| Methode | Zweck |
|---|---|
| `register_action(id, name, run, params, *, category, analog, threaded, description, summary)` | Neue Aktion. `run(mapping, ctx)` wird im Hintergrund ausgeführt. |
| `register_settings(params, on_change)` | Einstellungsfelder auf der Seite *Module*; `on_change(settings)` nach dem Speichern. |
| `settings` / `get_setting(key, default)` | Gespeicherte Einstellungen lesen. |
| `set_status(text)` | Status in der Modulliste anzeigen (z. B. „Verbunden“). |
| `on_unload(fn)` | Aufräumen beim Deaktivieren/Entfernen/Beenden (Threads stoppen!). |
| `run_in_gui(fn)` | Code im GUI-Thread ausführen (für Qt-Objekte). |
| `log` | Logger; die Ausgaben erscheinen unter *Protokoll*. |

**`ctx` (RunContext):** `input_key` (z. B. `btn_3`), `value` (Position 0–100 bei Slider/Poti, sonst `None`), `multiplier` (Encoder-Rastungen).

**`analog=True`:** Die Aktion kann auf die *Position* eines Sliders oder Potis gelegt werden und erhält dann `ctx.value`.

**`threaded=True`:** Die Aktion bekommt einen eigenen Thread. Das ist für langsame Aufrufe wie Netzwerkanfragen gedacht, damit andere Tasten nicht warten müssen.

### Param-Typen

`text`, `url`, `password`, `multiline`, `int` (`minimum`/`maximum`), `bool`, `file`, `app`, `hotkey`, `choice`

Bei `choice` kann `choices` eine Liste `[(wert, anzeige), …]` oder eine Funktion sein, die so eine Liste liefert. Mit einer Funktion lässt sich die Liste live aktualisieren (Knopf ⟳ im Dialog).

## Verfügbare Bibliotheken

In der kompilierten App kann ein Modul die Python-Standardbibliothek sowie `PySide6`, `requests`, `websocket` (websocket-client), `psutil`, `pyautogui`, `serial` und `pycaw` nutzen. Weitere **reine** Python-Pakete legst du in den Ordner `lib/` des Moduls.

## Testen & Verpacken

- **Entwicklung:** Module in `plugins/` im Repo werden beim Start aus dem venv automatisch geladen (`python -m app`).
- **ZIP bauen:** `python scripts/package_plugins.py mein_modul` erzeugt `dist/plugins/mein_modul-<version>.zip`.
- **Installieren:** In der App unter **Module → Modul installieren (ZIP) …** die ZIP-Datei auswählen. Das Modul wird sofort geladen, ein Neustart ist nicht nötig.
