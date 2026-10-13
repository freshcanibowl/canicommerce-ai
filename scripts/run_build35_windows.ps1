# Build 3.5 offline verification on Windows PowerShell.
# Dedicated disposable LOCAL PostgreSQL only. No production database or live payments.
$ErrorActionPreference = "Stop"
if (-not $env:TEST_DATABASE_URL) { throw "TEST_DATABASE_URL is required" }
if ($env:CANICOMMERCE_DISPOSABLE_DB_ACK -ne "YES") {
  throw "Set CANICOMMERCE_DISPOSABLE_DB_ACK=YES only for a disposable dedicated test database"
}
try { $uri = [Uri]$env:TEST_DATABASE_URL } catch { throw "Invalid TEST_DATABASE_URL" }
if ($uri.Scheme -notin @("postgresql","postgres")) { throw "Only PostgreSQL DSNs allowed" }
if ($uri.Host -notin @("localhost","127.0.0.1","::1")) { throw "Refusing non-local PostgreSQL host" }
if ($uri.AbsolutePath.TrimStart("/") -ne "canicommerce_test") {
  throw "Refusing database other than canicommerce_test"
}
python -m pip install -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed" }
python -m pytest -q tests/test_core.py tests/test_payment_architecture.py
if ($LASTEXITCODE -ne 0) { throw "Core tests failed" }
python -m pytest -vv -ra tests/integration/test_worker_capture_execution.py tests/integration/test_worker_role.py
if ($LASTEXITCODE -ne 0) { throw "Worker capture tests failed" }
python -m pytest -q tests/integration
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL integration tests failed" }
Write-Host "Build 3.5 offline verification passed" -ForegroundColor Green
