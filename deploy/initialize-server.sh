#!/bin/bash
set -euo pipefail
cd /opt/iris-cm
umask 077
if [ ! -f production.env ]; then
  printf 'HCM_DEBUG=0\nHCM_ALLOWED_HOSTS=167.172.152.167,127.0.0.1,localhost\nHCM_SCRIPT_NAME=/cm\nHCM_SERVE_STATIC=1\nHCM_SEAL_KEY=/secrets/nfhs6.key\nHCM_SECRET_KEY=' > production.env
  openssl rand -hex 48 >> production.env
fi
mkdir -p secrets app/data/{raw,interim,processed,manual,geo,sealed} app/outputs app/docs app/model app/dist
chown -R 10001:10001 app secrets
docker run --rm --user 10001:10001 --env-file production.env -v /opt/iris-cm/app:/app iris-cm:20261009 python manage.py migrate --noinput
docker run --rm --user 10001:10001 --env-file production.env -v /opt/iris-cm/app:/app iris-cm:20261009 python manage.py setup_team > initial-logins.txt
docker run --rm --user 10001:10001 --env-file production.env -v /opt/iris-cm/app:/app iris-cm:20261009 python manage.py collectstatic --noinput
docker run -d --name iris-cm --restart unless-stopped --user 10001:10001 --env-file production.env -p 127.0.0.1:8091:8000 -v /opt/iris-cm/app:/app -v /opt/iris-cm/secrets:/secrets iris-cm:20261009
