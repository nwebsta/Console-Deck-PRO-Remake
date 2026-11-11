# Console Deck Pro – PC App

Desktop-Steuersoftware für das [Console Deck Pro](https://github.com/LucaDiLorenzo98/console_deck_pro). Die App verbindet sich mit dem Deck, führt die Aktionen aus, die auf Tasten und Regler gelegt sind, und lässt sich mit Modulen erweitern.

> 🚧 **Status:** in Entwicklung

## Features

- **Volle Kompatibilität** mit allen Funktionen der bisherigen PC-Software
- **Profile:** mehrere Tastenbelegungen (z. B. Gaming, Streaming, Arbeit), umschaltbar per Taste oder automatisch je nach aktivem Programm
- **System Tray:** beim Schließen optional in den Infobereich minimieren
- **Autostart:** optional mit Windows starten
- **Module:** Funktionen nachinstallieren, per ZIP-Import oder über den Plugin-Ordner

## Module

| Modul | Beschreibung | Status |
|---|---|---|
| Voicemod | Stimme wechseln, Voice Changer an/aus, Soundboard, Mikrofon stumm | geplant |

### Modul installieren

1. In der App **Module → Modul installieren** wählen und die `.zip`-Datei auswählen
2. *oder* den entpackten Modulordner nach `%APPDATA%\ConsoleDeckPro\plugins\` kopieren
3. App neu starten (falls nötig)

## Installation (Endnutzer)

Die aktuelle `ConsoleDeckPro.exe` unter [Releases](../../releases) herunterladen und starten. Python muss dafür nicht installiert sein.

## Entwicklung

### Voraussetzungen

- Windows 10/11
- Python 3.12+

### Setup

```powershell
git clone <repo-url>
cd <repo-ordner>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app
```

### Build (.exe)

```powershell
.\.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller build.spec
```

Die fertige App liegt danach in `dist/`.

### Eigenes Modul entwickeln

Ein Modul ist ein Ordner mit einer `plugin.json` (Name, Version, Beschreibung) und einem Python-Einstiegspunkt, der Aktionen für Tasten und Regler registriert. Eine ausführliche Anleitung folgt.

## Tech-Stack

- [PySide6](https://doc.qt.io/qtforpython/) (Qt) für Oberfläche und Tray
- [PyInstaller](https://pyinstaller.org/) für den Build

## Lizenz

*folgt*
