#!/bin/sh
# Moves a Compose stack's database from PostgreSQL 16 (volume pg_data) to
# PostgreSQL 18 (volume pg18_data). Run it once, from the directory with
# docker-compose.yml and .env, after switching to a Hubra version whose
# docker-compose.yml runs postgres:18:
#
#     scripts/pg-upgrade-18.sh
#
# It stops the stack, starts PostgreSQL 16 on the old volume and an empty
# PostgreSQL 18, copies everything across with pg_dumpall (roles with their
# passwords, every database, every club schema), compares the two, and
# starts the stack again. A copy of the dump stays in the current directory.
# The old volume is not changed: going back is the previous docker-compose.yml.
# docs/operator-guide.md, "PostgreSQL 18 (Compose)".
# The commands for the containers are in single quotes on purpose: they
# expand there, with the containers' own POSTGRES_* variables.
# shellcheck disable=SC2016
set -eu

dc() { docker compose "$@"; }
in18() { docker exec -i "$new" sh -c "$1"; }
in16() { dc --profile pg-upgrade exec -T postgres16 sh -c "$1"; }

# Where the data is now, read through the postgres service's mounts.
state=$(dc run --rm --no-deps -T --entrypoint sh postgres -c '
  if [ -s "$PGDATA/PG_VERSION" ]; then echo new
  elif [ -s /var/lib/postgresql/16-data/PG_VERSION ]; then cat /var/lib/postgresql/16-data/PG_VERSION
  else echo none; fi')
case "$state" in
  new) echo "PostgreSQL 18 already holds the data (pg18_data); nothing to do."; exit 0 ;;
  none) echo "No PostgreSQL 16 data in pg_data; a new stack starts on 18 by itself."; exit 0 ;;
  16) ;;
  *) echo "pg_data holds PostgreSQL $state data; this script only moves 16." >&2; exit 1 ;;
esac

echo "Stopping the stack ..."
dc stop

echo "Starting PostgreSQL 16 on pg_data and an empty PostgreSQL 18 on pg18_data ..."
dc --profile pg-upgrade up -d postgres16
# Only the superuser and the postgres database: everything else, the app
# role and Hubra's database included, comes from the dump.
new=$(dc run -d --no-deps -e HUBRA_PG_UPGRADE=1 -e POSTGRES_DB=postgres \
  -e POSTGRES_APP_USER= -e POSTGRES_APP_PASSWORD= postgres)
cleanup() {
  docker rm -f "$new" >/dev/null 2>&1 || true
  dc --profile pg-upgrade rm -sf postgres16 >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Over TCP: during its first start the 18 container runs a socket-only
# server for the init scripts, then restarts.
for _ in $(seq 60); do
  if in16 'pg_isready -q -h 127.0.0.1 -U "$POSTGRES_USER"' \
      && in18 'pg_isready -q -h 127.0.0.1 -U "$POSTGRES_USER"'; then
    break
  fi
  sleep 2
done
in16 'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER"'
in18 'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER"'

dump="pg16-dumpall-$(date +%Y%m%d-%H%M%S).sql"
echo "Dumping PostgreSQL 16 into $dump (pg_dumpall 18) ..."
umask 077
in18 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dumpall -h postgres16 -U "$POSTGRES_USER"' > "$dump"

echo "Restoring into PostgreSQL 18 ..."
# The superuser exists already (the 18 init made it); the dump's ALTER ROLE
# still gives it its old password. Any other error stops the restore.
in18 'sed -E "/^CREATE ROLE \"?$POSTGRES_USER\"?;\$/d" \
  | psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' < "$dump" >/dev/null

# Same roles, and every table with the same number of rows, on both sides.
summary=$(cat <<'SH'
psql -XAt -U "$POSTGRES_USER" -d postgres -c "SELECT 'role ' || rolname FROM pg_roles WHERE rolname !~ '^pg_' ORDER BY 1"
for db in $(psql -XAt -U "$POSTGRES_USER" -d postgres -c "SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY 1"); do
  psql -XAt -U "$POSTGRES_USER" -d "$db" -c "
    SELECT string_agg(format('SELECT %L, count(*) FROM %I.%I', current_database() || ' ' || n.nspname || '.' || c.relname, n.nspname, c.relname), ' UNION ALL ')
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r' AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'" \
  | psql -XAt -U "$POSTGRES_USER" -d "$db"
done | sort
SH
)
echo "Comparing ..."
before=$(in16 "$summary")
after=$(in18 "$summary")
if [ "$before" != "$after" ]; then
  echo "PostgreSQL 18 differs from 16; the stack stays stopped and pg_data is unchanged:" >&2
  printf '%s\n' "$before" > pg16-summary.txt
  printf '%s\n' "$after" > pg18-summary.txt
  diff pg16-summary.txt pg18-summary.txt >&2 || true
  exit 1
fi
echo "$(echo "$before" | grep -c '|') tables and $(echo "$before" | grep -c '^role ') roles match."

cleanup
trap - EXIT
echo "Starting the stack on PostgreSQL 18 ..."
dc up -d
cat <<MSG

Done. Check the stack (docs/operator-guide.md, Upgrade, step 5). The dump is in
$dump; delete it once you are happy (it holds every club's data). The old
volume pg_data is unchanged; once you no longer need the way back, empty it
with docker volume rm <project>_pg_data (docker volume ls shows the name).
Compose then keeps an empty pg_data, which the postgres service ignores.
MSG
