#!/bin/sh
# Apply migrations before starting the API. Set RUN_MIGRATIONS=false when running
# multiple replicas and migrating out-of-band (`alembic upgrade head`) instead.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    alembic upgrade head
fi

exec "$@"
