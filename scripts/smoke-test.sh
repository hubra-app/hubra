#!/bin/sh
# Smoke test of a running Compose stack: the apps answer, the SPA sends its
# security headers, a club admin can sign in, and the Celery processes run.
#
#   scripts/smoke-test.sh multi    # docker-compose.yml
#   scripts/smoke-test.sh single   # plus docker-compose.single-club.yml;
#                                  # needs ADMIN_EMAIL and ADMIN_PASSWORD in .env
set -eu

cd "$(dirname "$0")/.."
mode="${1:-multi}"
app="http://localhost:${FRONTEND_PORT:-8080}"
jar="$(mktemp)"
trap 'rm -f "$jar"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

env_value() {
  sed -n "s/^$1=//p" .env | tail -n 1
}

echo "Waiting for the API behind $app ..."
tries=0
until curl -fsS "$app/api/v1/instance" >/dev/null 2>&1; do
  tries=$((tries + 1))
  [ "$tries" -lt 90 ] || fail "the API did not answer within 3 minutes"
  sleep 2
done

instance="$(curl -fsS "$app/api/v1/instance")"
echo "instance: $instance"
echo "$instance" | grep -q "\"mode\":\"$mode\"" || fail "expected mode $mode"

headers="$(curl -fsSI "$app/")"
for h in content-security-policy x-frame-options x-content-type-options; do
  echo "$headers" | grep -qi "^$h:" || fail "the club app does not send $h"
done

if [ "$mode" = multi ]; then
  for port in "${ADMIN_FRONTEND_PORT:-8081}" "${SSO_FRONTEND_PORT:-8082}"; do
    curl -fsS -o /dev/null "http://localhost:$port/" || fail "nothing on port $port"
  done
  email=admin@smoke.test
  password="Smoke-Test-$(date +%s)!"
  docker compose exec -T backend flask provision-tenant \
    --name "Smoke Club" --slug smoke --admin-email "$email" --admin-password "$password" >/dev/null
  login_headers="-H X-Tenant-Slug:smoke"
else
  email="$(env_value ADMIN_EMAIL)"
  password="$(env_value ADMIN_PASSWORD)"
  [ -n "$email" ] && [ -n "$password" ] || fail "set ADMIN_EMAIL and ADMIN_PASSWORD in .env"
  login_headers=""
fi

body="$(printf '{"email":"%s","password":"%s"}' "$email" "$password")"
# shellcheck disable=SC2086 # login_headers is empty or one curl option
status="$(curl -sS -o /dev/null -w '%{http_code}' -c "$jar" $login_headers \
  -H 'Content-Type: application/json' -d "$body" "$app/api/v1/auth/login")"
[ "$status" = 200 ] || fail "sign-in answered $status"
for path in account/ modules/; do
  status="$(curl -sS -o /dev/null -w '%{http_code}' -b "$jar" "$app/api/v1/$path")"
  [ "$status" = 200 ] || fail "GET /api/v1/$path answered $status"
done

for svc in celery-worker celery-beat; do
  docker compose exec -T "$svc" python -c \
    "import sys; sys.exit(b'celery' not in open('/proc/1/cmdline', 'rb').read())" ||
    fail "$svc is not running Celery"
done

echo "Smoke test ($mode) passed."
