$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { py -3 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -e . -r requirements-app.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$env:CANICOMMERCE_DEMO_MODE = '1'
Write-Host 'Synthetic local demo: http://127.0.0.1:8766' -ForegroundColor Green
& .\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8766
