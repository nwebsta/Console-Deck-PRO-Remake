"""Packt jedes Modul aus plugins/ als installierbare ZIP-Datei nach dist/plugins/."""

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "plugins"


def package(folder: Path) -> Path:
    meta = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{meta['id']}-{meta['version']}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(folder.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                zf.write(f, Path(meta["id"]) / f.relative_to(folder))
    return target


if __name__ == "__main__":
    names = sys.argv[1:]
    for folder in sorted((ROOT / "plugins").iterdir()):
        if (folder / "plugin.json").exists() and (not names or folder.name in names):
            print(f"Modul: {package(folder)}")
