# PyInstaller-Spezifikation:  pyinstaller --noconfirm build.spec
from PyInstaller.utils.hooks import collect_submodules

# Bibliotheken, die Module (Plugins) zur Laufzeit nutzen dürfen, müssen in der .exe stecken.
hidden = (
    collect_submodules("app")
    + collect_submodules("websocket")
    + collect_submodules("pycaw")
    + ["comtypes.stream", "requests", "json", "uuid", "sqlite3", "xml.etree.ElementTree"]
)

excludes = [
    "tkinter",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtPdf", "PySide6.QtDesigner",
]

a = Analysis(
    ["app/__main__.py"],
    pathex=["."],
    hiddenimports=hidden,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="ConsoleDeckPro",
    icon="assets/icon.ico",
    console=False,
    upx=False,
    version=None,
)
