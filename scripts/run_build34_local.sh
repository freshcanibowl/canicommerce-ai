#!/usr/bin/env bash
# Local-only test runner. Requires disposable PostgreSQL and TEST_DATABASE_URL.
set -euo pipefail
: "${TEST_DATABASE_URL:?Set TEST_DATABASE_URL to a disposable, dedicated PostgreSQL database}"
case "$TEST_DATABASE_URL" in
  *localhost*|*127.0.0.1*) ;;
  *) echo "Refusing non-local database URL" >&2; exit 2 ;;
esac
if [[ "${CANICOMMERCE_DISPOSABLE_DB_ACK:-}" != "YES" ]]; then
  echo "Disposable database acknowledgement required" >&2
  exit 2
fi
python -c 'import os,urllib.parse; u=urllib.parse.urlsplit(os.environ["TEST_DATABASE_URL"]); assert u.scheme in ("postgres","postgresql") and u.hostname in ("localhost","127.0.0.1","::1") and urllib.parse.unquote(u.path)=="/canicommerce_test", "Refusing unsafe database target"'
python -m pip install -e '.[test]'
python -m pytest -q tests/test_core.py tests/test_payment_architecture.py
python -m pytest -vv -ra tests/integration/test_worker_capture_execution.py tests/integration/test_worker_role.py
python -m pytest -q tests/integration
echo "Build 3.6 offline checks completed."
