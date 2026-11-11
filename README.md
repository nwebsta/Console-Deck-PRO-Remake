# Console Deck Pro – PC App

Desktop-Steuersoftware für das [Console Deck Pro](https://github.com/LucaDiLorenzo98/console_deck_pro). Die App verbindet sich mit dem Deck, führt die Aktionen aus, die auf Tasten und Regler gelegt sind, und lässt sich mit Modulen erweitern.

Sie ersetzt das bisherige Gespann aus Python-Backend und Flutter-UI durch **eine** App mit Tray-Symbol und Autostart.

## Features

- **Kompatibel mit der bisherigen PC-Software:** gleiches serielles Protokoll und gleiche Firmware. Die Display-Statistiken (CPU, RAM, GPU, Uhrzeit, Datum) funktionieren wie bisher, und die alte `config.json` wird beim ersten Start automatisch übernommen.
- **Belegbar sind:**
  - 9 Haupttasten
  - der Drehregler (drücken, links und rechts drehen)
  - die Zusatztasten
  - Slider und Potis: entweder die Position (z. B. für die Lautstärke) oder „hoch/runter“ als einzelne Aktionen
- **Aktionen:** Webseite, Programm, Tastenkombination (mit Aufnahme-Funktion), Text tippen (inkl. Umlaute/Emoji), Mediensteuerung, Lautstärke (setzen, ändern, stumm), Sound abspielen, Bildschirmhelligkeit, Home Assistant und Profilwechsel
- **Profile:** mehrere Belegungen (z. B. Gaming, Streaming, Arbeit), umschaltbar per Taste, Tray-Menü oder **automatisch je nach Programm im Vordergrund**
- **System Tray:** beim Schließen optional in den Infobereich minimieren, auf Wunsch minimiert starten
- **Autostart:** optional mit Windows starten
- **Live-Ansicht:** gedrückte Tasten und Slider-Werte leuchten in der App auf
- **Module:** Funktionen per ZIP nachinstallieren, ohne Neustart

## Module

| Modul | Beschreibung |
|---|---|
| **Voicemod** | Stimme laden, nächste/vorherige/zufällige Stimme, Voice Changer an/aus, Mich-selbst-hören, Hintergrundeffekte, Soundboard (abspielen/stoppen), Mikrofon stumm |

### Modul installieren

1. Die `.zip`-Datei des Moduls herunterladen (z. B. `voicemod-1.0.0.zip` aus den [Releases](../../releases)).
2. In der App **Module → Modul installieren (ZIP) …** wählen und die Datei auswählen.
3. Bei Bedarf das Modul einrichten, z. B. den Voicemod-Client-Key eintragen.

Installierte Module liegen in `%APPDATA%\ConsoleDeckPro\plugins\`.

### Voicemod einrichten

Die App steuert Voicemod über die offizielle **Voicemod Control API**. Dafür brauchst du einen Client-Key. Den gibt es kostenlos im [Voicemod Developer Portal](https://control-api.voicemod.net). Den Key trägst du unter **Module → Voicemod → Einstellungen** ein. Voicemod muss laufen.

## Installation (Endnutzer)

1. `ConsoleDeckPro.exe` aus den [Releases](../../releases) herunterladen und starten. Python muss dafür nicht installiert sein.
2. Unter **Einstellungen → Verbindung** den COM-Port des Decks wählen.
3. Unter **Deck** auf eine Taste klicken und eine Aktion festlegen.

> Die alte PC-Software (`console_deck_pro.py` bzw. deren Dienst) bitte vorher beenden, da immer nur ein Programm den COM-Port benutzen kann.

## Entwicklung

### Voraussetzungen

- Windows 10/11
- Python 3.12+

### Setup

```powershell
git clone https://github.com/nwebsta/Console-Deck-PRO-Remake.git
cd Console-Deck-PRO-Remake
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

Im Entwicklungsmodus werden die Module aus dem Ordner `plugins/` automatisch mitgeladen. Mit `CONSOLE_DECK_PRO_DIR=<ordner>` nutzt die App einen eigenen Datenordner, z. B. zum Testen.

### Build (.exe)

```powershell
.\scripts\build.ps1
```

Das Ergebnis liegt in `dist/`: `ConsoleDeckPro.exe` und die Modul-ZIPs in `dist/plugins/`.

### Projektstruktur

```
app/
├── main.py            Start, Single-Instance, Verdrahtung
├── config.py          Einstellungen & Profile (settings.json, Migration der alten config.json)
├── engine.py          Eingaben → Aktionen des aktiven Profils
├── plugins.py         Module laden/installieren/entfernen
├── plugin_api.py      Schnittstelle für Module
├── autostart.py       Windows-Autostart
├── focus_watcher.py   automatischer Profilwechsel
├── actions/           eingebaute Aktionen, Ausführung im Hintergrund
├── device/            serielles Protokoll, Verbindung, PC-Statistiken
└── ui/                Oberfläche (PySide6)
plugins/voicemod/      Voicemod-Modul
docs/MODULE.md         eigene Module entwickeln
```

### Eigenes Modul entwickeln

Siehe [docs/MODULE.md](docs/MODULE.md).

## Daten

| Was | Wo |
|---|---|
| Einstellungen & Profile | `%APPDATA%\ConsoleDeckPro\settings.json` |
| Module | `%APPDATA%\ConsoleDeckPro\plugins\` |
| Logdateien | `%APPDATA%\ConsoleDeckPro\logs\` |

## Tech-Stack

- [PySide6](https://doc.qt.io/qtforpython/) (Qt) für Oberfläche, Tray und Audio
- [pyserial](https://pyserial.readthedocs.io/) für die Verbindung zum Deck
- [pycaw](https://github.com/AndreMiras/pycaw) für die Lautstärke, [screen-brightness-control](https://github.com/Crozzers/screen_brightness_control) für die Helligkeit
- [PyInstaller](https://pyinstaller.org/) für den Build

## Lizenz

*folgt*
