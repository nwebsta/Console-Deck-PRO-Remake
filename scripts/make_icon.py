"""Erzeugt assets/icon.ico für den Build aus dem gezeichneten App-Icon."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.icon import make_pixmap  # noqa: E402

app = QApplication([])
out = ROOT / "assets" / "icon.ico"
out.parent.mkdir(exist_ok=True)
if not make_pixmap(256).save(str(out), "ICO"):
    sys.exit("Icon konnte nicht gespeichert werden")
print(f"Icon: {out}")
