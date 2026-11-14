#!/bin/bash
# If either process exits, stop the other and fail, so Docker never keeps a half-working container.
set -u

cd /srv/api
alembic upgrade head || exit 1

uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers --timeout-graceful-shutdown 30 &
api=$!
(cd /srv/web && HOSTNAME=0.0.0.0 PORT=3000 exec node server.js) &
web=$!

trap 'kill -TERM "$api" "$web" 2>/dev/null' TERM INT

wait -n "$api" "$web"
status=$?
kill -TERM "$api" "$web" 2>/dev/null
wait
exit "$((status == 0 ? 1 : status))"
