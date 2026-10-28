#!/bin/sh
# Smoke test of a running Compose stack: the apps answer, the SPA sends its
# security headers, a club admin can sign in, and the Celery processes run.
#
#   scripts/smoke-test.sh
set -eu

cd "$(dirname "$0")/.."
app="http://localhost:${FRONTEND_PORT:-8080}"
jar="$(mktemp)"
trap 'rm -f "$jar"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

echo "Waiting for the API behind $app ..."
tries=0
until curl -fsS "$app/api/v1/instance" >/dev/null 2>&1; do
  tries=$((tries + 1))
  [ "$tries" -lt 90 ] || fail "the API did not answer within 3 minutes"
  sleep 2
done

echo "instance: $(curl -fsS "$app/api/v1/instance")"

headers="$(curl -fsSI "$app/")"
for h in content-security-policy x-frame-options x-content-type-options; do
  echo "$headers" | grep -qi "^$h:" || fail "the club app does not send $h"
done

for port in "${ADMIN_FRONTEND_PORT:-8081}" "${SSO_FRONTEND_PORT:-8082}"; do
  curl -fsS -o /dev/null "http://localhost:$port/" || fail "nothing on port $port"
done
email=admin@smoke.test
password="Smoke-Test-$(date +%s)!"
docker compose exec -T backend flask provision-tenant \
  --name "Smoke Club" --slug smoke --admin-email "$email" --admin-password "$password" >/dev/null

body="$(printf '{"email":"%s","password":"%s"}' "$email" "$password")"
status="$(curl -sS -o /dev/null -w '%{http_code}' -c "$jar" -H X-Tenant-Slug:smoke \
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

echo "Smoke test passed."
