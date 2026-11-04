#!/bin/sh
# Clubs and accounts for the browser tests (app/frontend/e2e) on a running
# Compose stack. One club and one platform-admin account per Playwright
# worker, so parallel workers never see each other's changes. The names
# follow app/frontend/e2e/env.ts: worker 1 uses E2E_CLUB and E2E_EMAIL as
# they are, worker n (n >= 2) the club "<E2E_CLUB>-n" and the account
# "<name>-n@<domain>". All accounts get E2E_PASSWORD.
#
#   E2E_WORKERS=3 E2E_PASSWORD=... scripts/e2e-accounts.sh
set -eu

cd "$(dirname "$0")/.."
: "${E2E_PASSWORD:?set E2E_PASSWORD}"
workers="${E2E_WORKERS:-1}"
club="${E2E_CLUB:-e2e}"
email="${E2E_EMAIL:-e2e@hubra.test}"

admins=""
n=1
while [ "$n" -le "$workers" ]; do
  if [ "$n" -eq 1 ]; then
    slug="$club" name="E2E Club" mail="$email"
  else
    slug="$club-$n" name="E2E-$n Club" mail="${email%@*}-$n@${email#*@}"
  fi
  docker compose exec -T backend flask provision-tenant \
    --name "$name" --slug "$slug" --admin-email "$mail" --admin-password "$E2E_PASSWORD"
  admins="${admins:+$admins,}$mail"
  n=$((n + 1))
done
docker compose exec -T -e SUPERADMIN_EMAILS="$admins" backend flask ensure-superadmins
