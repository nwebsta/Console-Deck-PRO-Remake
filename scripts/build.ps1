# Baut ConsoleDeckPro.exe und die Modul-ZIPs nach dist/
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q -r requirements.txt -r requirements-dev.txt
& $py scripts\make_icon.py
& $py -m PyInstaller --noconfirm --clean build.spec
& $py scripts\package_plugins.py
Write-Host "Fertig: dist\ConsoleDeckPro.exe und dist\plugins\" -ForegroundColor Green
