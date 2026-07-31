<#
.SYNOPSIS
    Starts the SkillAtlas backend and frontend together.

.EXAMPLE
    .\run-dev.ps1
    .\run-dev.ps1 -Setup      # also installs deps, migrates and seeds first
#>
param(
    [switch]$Setup
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No venv found. Creating one..." -ForegroundColor Yellow
    py -3 -m venv (Join-Path $backend "venv")
}

if ($Setup) {
    Write-Host "`n=== Installing backend dependencies ===" -ForegroundColor Cyan
    & $python -m pip install -r (Join-Path $backend "requirements.txt") --disable-pip-version-check

    if (-not (Test-Path (Join-Path $backend ".env"))) {
        Copy-Item (Join-Path $backend ".env.example") (Join-Path $backend ".env")
        Write-Host "Created backend\.env from .env.example" -ForegroundColor Yellow
    }

    Write-Host "`n=== Applying migrations ===" -ForegroundColor Cyan
    Push-Location $backend; & $python -m alembic upgrade head; Pop-Location

    Write-Host "`n=== Seeding content ===" -ForegroundColor Cyan
    Push-Location $backend; & $python -m app.seed.loader; Pop-Location

    Write-Host "`n=== Installing frontend dependencies ===" -ForegroundColor Cyan
    Push-Location $frontend; npm install; Pop-Location
}

Write-Host "`nStarting backend on http://localhost:8010 (docs at /docs)" -ForegroundColor Green
$api = Start-Process -PassThru -WorkingDirectory $backend -FilePath $python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8010"

Write-Host "Starting frontend on http://localhost:3000" -ForegroundColor Green
$web = Start-Process -PassThru -WorkingDirectory $frontend -FilePath "npm.cmd" `
    -ArgumentList "run", "dev"

Write-Host "`nBoth servers running. Press Ctrl+C to stop." -ForegroundColor Cyan
try {
    Wait-Process -Id $api.Id, $web.Id
}
finally {
    foreach ($p in @($api, $web)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}
