#!/bin/sh
# Create the secrets that stay out of git. Run once per cluster, and again after
# changing .env (then `kubectl -n hubra rollout restart deployment`).
#
#   GHCR_USER=<github login> GHCR_TOKEN=<token with read:packages> deploy/create-secrets.sh
#
# Secret hubra-env:             every KEY= in .env, DATABASE_URL pointed at the postgres Service
# Secret ghcr-pull:             if GHCR_USER/GHCR_TOKEN are set (needed while the images are private)
# Secret cloudflare-credentials: if modules/mail/certbot/cloudflare.ini exists (mail module)
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
NS=hubra

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"
apply() { kubectl -n "$NS" "$@" --dry-run=client -o yaml | kubectl apply -f -; }

# Load .env the way a shell would (strips comments, resolves ${VAR}), then
# write it back out as plain KEY=value lines for kubectl.
set +u -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set -u +a
env_out="$(mktemp)"
trap 'rm -f "$env_out"' EXIT INT TERM
sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' "$ENV_FILE" | sort -u | grep -vx DATABASE_URL |
  while read -r key; do printf '%s=%s\n' "$key" "$(printenv "$key" || true)"; done > "$env_out"
echo "DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:${POSTGRES_PORT:-5432}/$POSTGRES_DB" >> "$env_out"
apply create secret generic hubra-env --from-env-file="$env_out"

if [ -n "${GHCR_USER:-}" ]; then
  apply create secret docker-registry ghcr-pull --docker-server=ghcr.io \
    --docker-username="$GHCR_USER" --docker-password="$GHCR_TOKEN"
fi

if [ -f "$ROOT/modules/mail/certbot/cloudflare.ini" ]; then
  apply create secret generic cloudflare-credentials \
    --from-file=cloudflare.ini="$ROOT/modules/mail/certbot/cloudflare.ini"
fi
