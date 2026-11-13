#!/bin/sh
# Entrypoint of the Compose postgres service (PostgreSQL 18). A stack that
# ran PostgreSQL 16 keeps that data in the old volume (pg_data, mounted
# read-only at /var/lib/postgresql/16-data). Without this check, the first
# start on 18 would set up an empty database next to it and Hubra would come
# up as a new install. scripts/pg-upgrade-18.sh moves the data over.
set -eu

old=/var/lib/postgresql/16-data
if [ ! -s "$PGDATA/PG_VERSION" ] && [ -s "$old/PG_VERSION" ] \
    && [ "${HUBRA_PG_UPGRADE:-}" != 1 ]; then
  cat >&2 <<MSG
The database is still in the PostgreSQL $(cat "$old/PG_VERSION") volume (pg_data), and the
PostgreSQL 18 volume (pg18_data) is empty. Move the data over first, from the
directory with docker-compose.yml and .env:

    scripts/pg-upgrade-18.sh

docs/operator-guide.md, "PostgreSQL 18 (Compose)", has the details.
MSG
  exit 1
fi

exec docker-entrypoint.sh "$@"
