#!/bin/sh
# One-time upgrade for stacks that predate the app DB role: creates the role
# (idempotent), grants it the database, and hands it ownership of the app's
# schemas, tables and sequences, so that later migrations run by the app can
# still ALTER them. Run it inside the postgres container:
#
#   docker compose exec postgres sh /pg-upgrade/pg-app-role-upgrade.sh
#
# or copy it in first:
#
#   docker compose cp scripts/pg-app-role-upgrade.sh postgres:/tmp/
#   docker compose exec postgres sh /tmp/pg-app-role-upgrade.sh
#
# Afterwards set POSTGRES_APP_USER and POSTGRES_APP_PASSWORD in .env (the
# same values this script saw) and restart the stack.
set -eu

: "${POSTGRES_APP_USER:?set POSTGRES_APP_USER}" "${POSTGRES_APP_PASSWORD:?set POSTGRES_APP_PASSWORD}"

psql -v ON_ERROR_STOP=1 \
  -v app_user="$POSTGRES_APP_USER" -v app_password="$POSTGRES_APP_PASSWORD" \
  -v db="$POSTGRES_DB" \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB CREATEROLE NOREPLICATION', :'app_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec
ALTER ROLE :"app_user" LOGIN PASSWORD :'app_password';
-- Club roles (docs/club-db-roles.md): the app makes one per club.
ALTER ROLE :"app_user" CREATEROLE;
GRANT CREATE, CONNECT, TEMP ON DATABASE :"db" TO :"app_user";

-- The app's schemas: public and one per club. Everything in them moves to
-- the app role, so its migrations can keep altering the tables.
SELECT format('ALTER SCHEMA %I OWNER TO %I', nspname, :'app_user')
FROM pg_namespace
WHERE nspname LIKE 'tenant\_%' \gexec
GRANT ALL ON SCHEMA public TO :"app_user";

SELECT format('ALTER TABLE %I.%I OWNER TO %I', schemaname, tablename, :'app_user')
FROM pg_tables
WHERE schemaname = 'public' OR schemaname LIKE 'tenant\_%' \gexec

SELECT format('ALTER SEQUENCE %I.%I OWNER TO %I', schemaname, sequencename, :'app_user')
FROM pg_sequences
WHERE schemaname = 'public' OR schemaname LIKE 'tenant\_%' \gexec
SQL

echo "Role $POSTGRES_APP_USER ready. Now put POSTGRES_APP_USER/POSTGRES_APP_PASSWORD in .env and restart."
