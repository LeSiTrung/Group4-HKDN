param([switch]$Check)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Project Python missing. Follow README.md to create backend/.venv and install requirements-dev.txt.'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'frontend/dist/index.html'))) {
    throw 'Frontend build missing. Run npm ci and npm run build inside frontend first.'
}
Push-Location (Join-Path $PSScriptRoot 'backend')
try {
    @'
import fastapi, uvicorn, pydantic, dotenv, httpx, bs4, pwdlib, qdrant_client, fastembed, tzdata
from app.main import app
assert any(getattr(route, 'name', '') == 'frontend' for route in app.routes)
print('Project dependencies and frontend build found.')
'@ | & $python -
    if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed. Install backend/requirements-dev.txt in the project venv.' }
    if (-not $Check) {
        & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers --no-access-log
        if ($LASTEXITCODE -ne 0) { throw 'Application exited with an error. Check the error above and whether port 8000 is occupied.' }
    }
} finally { Pop-Location }
