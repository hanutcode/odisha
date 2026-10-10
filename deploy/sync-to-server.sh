#!/bin/bash
# Push this project's code and data to the /cm/ server, then restart and check it.
# Run from the project folder on the Mac:   ./deploy/sync-to-server.sh
# Needs your SSH access to the server as root. Safe to re-run.
#
# Nothing on the server is deleted: files people uploaded there stay.
# Never sent: the web database (production keeps its own users/passwords), secret key,
# password files, the NFHS-6 key, .venv, .git, caches, MOCK outputs and built HTML.
# The old encrypted NFHS-6 bundle on the server is left alone; the opened NFHS-6 file
# (data/raw/nfhs/round6/) and the seal history (docs/seal_log.jsonl) are sent.
set -euo pipefail
HOST=${HOST:-root@167.172.152.167}
APP=/opt/iris-cm/app
cd "$(dirname "$0")/.."

echo "1/5 Backing up the server app folder (code and data, not the database)…"
ssh "$HOST" "mkdir -p /opt/iris-cm/backups && cd /opt/iris-cm && \
  tar czf backups/app-before-sync-\$(date +%Y%m%d-%H%M).tgz --exclude=app/web/workspace.sqlite3 app && \
  cp app/web/workspace.sqlite3 backups/workspace-\$(date +%Y%m%d-%H%M).sqlite3"

echo "2/5 Copying code and data…"
rsync -az --itemize-changes \
  --exclude='.git/' --exclude='.venv/' --exclude='__pycache__/' --exclude='.pytest_cache/' --exclude='.DS_Store' \
  --exclude='web/workspace.sqlite3' --exclude='web/.secret_key' --exclude='web/.initial_passwords.json' \
  --exclude='web/.preset_applied' --exclude='web/staticfiles/' --exclude='.deploy-logins.txt' --exclude='*.key' \
  --exclude='data/sealed/' --exclude='data/unsealed/' \
  --exclude='outputs/' --exclude='dist/' --exclude='Start IRIS Workspace.command' \
  ./ "$HOST:$APP/" | grep -v '^\.' | tail -40 || true

echo "3/5 Fixing ownership and rebuilding static files and the DuckDB file…"
ssh "$HOST" "chown -R 10001:10001 $APP && \
  docker exec iris-cm python manage.py collectstatic --noinput -v0 && \
  docker exec iris-cm python manage.py remove_former_members && \
  docker exec -w /app iris-cm sh -c 'PYTHONPATH=src python -m hcm panel' | tail -4"

echo "4/5 Restarting…"
ssh "$HOST" "docker restart iris-cm >/dev/null && sleep 5 && docker exec iris-cm python manage.py check"

echo "5/5 Checking the live site…"
ssh "$HOST" "curl -s -o /dev/null -w 'login %{http_code}\n' http://127.0.0.1:8091/login/ && \
  curl -s http://127.0.0.1:8091/fair/ | grep -q 'insights-data' && echo 'fair dashboard: OK' && \
  curl -s http://127.0.0.1:8091/fair/map/ | grep -q '\"mode\":\"survey\"' && echo 'fair map: survey mode, no MOCK' && \
  docker exec -w /app iris-cm python -c \"import pandas as pd; w=pd.read_parquet('data/processed/panel_wide.parquet'); o=w[w.state.str.contains('Odisha',case=False)]; print('panel rows', len(w), '| Odisha districts', o.unit_id.nunique(), '| rain years', int(o.rain_mm.notna().groupby(o.year).any().sum()))\""
echo "Done. Roll back with the tarball in /opt/iris-cm/backups if anything looks wrong."
