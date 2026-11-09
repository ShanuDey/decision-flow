#!/bin/bash
# Runs the API and the web server in one container. If either exits, stop the other and
# exit non-zero so Docker sees the failure instead of a half-working container.
set -u

cd /srv/api
alembic upgrade head || exit 1

uvicorn app.main:app --host 0.0.0.0 --port 8000 &
api=$!
(cd /srv/web && HOSTNAME=0.0.0.0 PORT=3000 exec node server.js) &
web=$!

trap 'kill -TERM "$api" "$web" 2>/dev/null' TERM INT

wait -n "$api" "$web"
status=$?
kill -TERM "$api" "$web" 2>/dev/null
wait
exit "$((status == 0 ? 1 : status))"
