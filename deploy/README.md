# IRIS CM server deployment

URL: http://167.172.152.167/cm/

The fresh installation uses `/opt/iris-cm/app` as persistent application storage,
Docker image `iris-cm:20261009`, container `iris-cm`, and loopback port 8091.
Apache routes `/cm/` using `/etc/httpd/conf.d/cm.conf`. Other sites retain their routing.
The container runs as UID 10001 and restarts automatically.

Production settings are in `/opt/iris-cm/production.env` (root-only).
Initial account passwords are in `/opt/iris-cm/initial-logins.txt` (root-only).
Use Change password after first sign-in. HTTP is currently used as requested.

This is a code-only fresh installation: local research inputs, derived data,
model outputs, documents, database, and seal keys have not been migrated.
The fair map now includes a minimal survey panel: 60 NFHS-4/5 observations
for 30 Odisha districts, plus the Odisha district boundaries. Other inputs
must be uploaded before running the full pipeline.
The research model and its Git freeze history must be installed separately before
using the model freeze/unseal workflow.

Useful server commands:

```sh
docker logs --tail 100 iris-cm
docker restart iris-cm
docker exec iris-cm python manage.py check
```

Before changes, back up the app directory, production environment, and secrets.
Do not rerun the initialization script over an existing deployment.
The previous static page remains in `/var/www/cm`; its Apache config is backed up
under `/opt/iris-cm/backups/`. To roll back routing, restore that `cm.conf`, run
`httpd -t`, then `systemctl reload httpd`.

## Data migration, 2026-10-09

Local source uploads, manual inputs, geography, processed panel, seal/audit logs,
13 contribution entries and 9 checklist items were migrated after explicit approval.
The encrypted NFHS-6 bundle was copied; its decryption key remains local.
Production passwords were preserved. Source counts match local: NFHS-4 30,
NFHS-5 30, NFHS-6 sealed bundle 1, NCRB 9, UDISE 10.
DuckDB was rebuilt from the migrated Parquet files.

## MOCK outputs hidden, 2026-10-09

Production never shows MOCK model outputs: with `HCM_DEBUG=0`, `HCM_ALLOW_MOCK`
defaults to off, so both the workspace map and `/fair/map/` show the published NFHS-4/5
survey map until Hanut uploads real outputs. `/fair/map/` and the `/fair/` dashboard never show MOCK.
Push this change with `./deploy/update-hide-mock.sh` (backs up the five files first).

## Full data and code sync, 2026-10-10

`./deploy/sync-to-server.sh` (run on the Mac, needs root SSH) backs up `/opt/iris-cm/app`
and the web database, copies code and data (never the database, secrets, password files,
NFHS-6 key or sealed bundle, MOCK outputs), rebuilds the panel/DuckDB in the container,
restarts it and checks the login page, the fair map (survey mode) and the panel coverage.
It replaces `update-hide-mock.sh`. Set `HCM_HTTPS=1` in `production.env` only after Apache
serves the site over HTTPS.

## Complete deployment, 2026-10-10

The current container uses `iris-cm:20261010-full`. Its Dockerfile installs the
web, pipeline and model requirements, plus a C++ compiler for PyTensor. `HOME=/tmp`
provides writable library caches for UID 10001.

The project code, research model files, source/processed data and validated current
`outputs/district_estimates.csv` and `outputs/reason_codes.csv` were deployed.
The model run ID in those supplied outputs is `uncommitted` (30 districts, four
flagged); deployment does not rerun inference or change the research results.
The panel and offline map were regenerated on the server. Production accounts,
passwords, database and secrets were retained. Local mock archives, local credentials,
virtual environments and seal keys were excluded.

Rollback backup: `/opt/iris-cm/backups/full-20261010-125821/` contains the application,
a consistent SQLite backup, production environment and previous container configuration.
The prior container `iris-cm-before-20261010-130201` is stopped and retained.
Activation and smoke-check scripts are `/opt/iris-cm/activate-20261010.sh` and
`/opt/iris-cm/verify-deployment.py` on the server.

The older `sync-to-server.sh` excludes all outputs and expects survey mode; it is
not the complete-deployment procedure. For subsequent full deployments, rebuild
the image, validate and copy current non-MOCK outputs, and regenerate the map.
