#!/usr/bin/env bash
# Start the IRIS team workspace on this Mac: http://localhost:8000
# Safe to run every time: installs anything missing, then starts the server.
set -euo pipefail
cd "$(dirname "$0")"

# Prefer a newer Python if one is installed; macOS's built-in 3.9 also works.
PY=${PYTHON:-}
if [ -z "$PY" ]; then
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
  done
fi
if [ -z "$PY" ]; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/macos/ and run this again."
  exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || {
  echo "Python 3.9 or newer is needed (found $("$PY" --version))."; exit 1; }

if [ ! -x .venv/bin/python ]; then
  echo "Creating .venv with $("$PY" --version)…"
  "$PY" -m venv .venv
fi

if ! .venv/bin/python -c "import django, pandas, geopandas, duckdb, rapidfuzz, cryptography, pdfplumber" >/dev/null 2>&1; then
  echo "Installing packages (first run only, a few minutes)…"
  .venv/bin/python -m pip install -U pip
  .venv/bin/python -m pip install -r requirements-web.txt
fi

cd web
../.venv/bin/python manage.py migrate -v0
../.venv/bin/python manage.py setup_team
# One time only: make the accounts match the passwords listed on the login page
if [ -f .initial_passwords.json ] && [ ! -f .preset_applied ]; then
  ../.venv/bin/python manage.py setup_team --apply-preset && date > .preset_applied
fi
../.venv/bin/python manage.py check

HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8000}
echo ""
echo "Workspace:  http://localhost:${PORT}/"
echo "Fair map:   http://localhost:${PORT}/fair/   (no sign-in)"
echo "Keep this window open. Stop with Ctrl+C."
exec ../.venv/bin/python manage.py runserver "${HOST}:${PORT}"
