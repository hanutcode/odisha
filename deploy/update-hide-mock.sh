#!/bin/bash
# Pushes the "never show MOCK in production" fix to the /cm/ server and restarts it.
# Run from this project folder on the Mac:  ./deploy/update-hide-mock.sh  (needs your SSH access as root)
set -euo pipefail
HOST=${HOST:-root@167.172.152.167}
APP=/opt/iris-cm/app
FILES="web/iris_web/settings.py web/workspace/services.py web/workspace/views.py web/workspace/tests.py web/workspace/templates/workspace/map.html"
cd "$(dirname "$0")/.."
ssh "$HOST" "cd $APP && tar czf /opt/iris-cm/backups/pre-hide-mock-\$(date +%Y%m%d%H%M).tgz $FILES"
tar czf - $FILES | ssh "$HOST" "cd $APP && tar xzf - && chown -R 10001:10001 web"
ssh "$HOST" "docker restart iris-cm >/dev/null && sleep 4 && docker exec iris-cm python manage.py check && \
  curl -s http://127.0.0.1:8091/fair/map/ | grep -q '\"mode\":\"survey\"' && echo 'Fair map: survey mode, no MOCK.'"
