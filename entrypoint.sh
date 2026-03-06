#!/bin/sh
set -e

PORT="${PORT:-8000}"
echo "Starting gunicorn on port $PORT ..."

exec gunicorn wsgi:app \
  --workers 2 \
  --bind "0.0.0.0:${PORT}" \
  --timeout 120 \
  --log-level debug \
  --access-logfile - \
  --error-logfile -