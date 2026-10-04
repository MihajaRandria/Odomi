# launch.ps1 - Lance le serveur de developpement local (FastAPI + Dash).
# Usage : .\launch.ps1   (fonctionne quel que soit le dossier courant)
Set-Location -Path $PSScriptRoot

$venvUvicorn = Join-Path $PSScriptRoot ".venv\Scripts\uvicorn.exe"
if (Test-Path $venvUvicorn) {
    & $venvUvicorn main:app --host 0.0.0.0 --port 8000 --reload
} else {
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
}