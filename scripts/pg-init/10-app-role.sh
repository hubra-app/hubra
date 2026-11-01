#!/bin/sh
# Runs once when the postgres container initialises a fresh data volume
# (docker-entrypoint-initdb.d). Creates the role the app connects as: it can
# create schemas and tables in its own database but is no superuser, so a
# compromised backend or plugin cannot touch the cluster beyond its data.
#
# Existing stacks (the volume already holds data) run
# scripts/pg-app-role-upgrade.sh once instead.
set -eu

if [ -z "${POSTGRES_APP_USER:-}" ] || [ -z "${POSTGRES_APP_PASSWORD:-}" ]; then
  echo "POSTGRES_APP_USER/POSTGRES_APP_PASSWORD not set; the app connects as $POSTGRES_USER." >&2
  exit 0
fi

psql -v ON_ERROR_STOP=1 \
  -v app_user="$POSTGRES_APP_USER" -v app_password="$POSTGRES_APP_PASSWORD" \
  -v db="$POSTGRES_DB" \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT CREATE, CONNECT, TEMP ON DATABASE :"db" TO :"app_user";
GRANT ALL ON SCHEMA public TO :"app_user";
SQL
