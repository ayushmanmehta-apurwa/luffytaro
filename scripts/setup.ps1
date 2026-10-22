# One-time setup for Windows PowerShell: python venv + backend dependencies + frontend dependencies.
# If scripts are blocked, run once in this window:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) { Copy-Item .env.example backend\.env }
Push-Location frontend; npm install; Pop-Location
Push-Location backend; python init_db.py; Pop-Location
Write-Host ""
Write-Host "Done. Start the app in two PowerShell windows:"
Write-Host "  1) .\.venv\Scripts\Activate.ps1; cd backend; uvicorn app.main:app --reload --port 8000"
Write-Host "  2) cd frontend; npm run dev        (then open http://localhost:5173)"
