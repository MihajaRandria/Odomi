# create.ps1 - Initialisation locale Windows :
#   1. creation du venv .venv (si absent)
#   2. installation des dependances (requirements.txt)
#   3. telechargement des assets hors-ligne (static/vendor)
# Usage : .\create.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creation de l'environnement virtuel .venv ..."
    python -m venv .venv
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt
& $venvPython setup_offline.py

Write-Host ""
Write-Host "Installation terminee. Lancez le serveur avec : .\launch.ps1"