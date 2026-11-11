import sys
from pathlib import Path

if not __package__:
    # Direkt als Datei gestartet (z. B. über Autostart mit pythonw): Projektwurzel in den Pfad.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
