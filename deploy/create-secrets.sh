#!/bin/sh
# Create the secrets that stay out of git. Run once per cluster, and again after
# changing .env (then `kubectl -n hubra rollout restart deployment`).
#
#   GHCR_USER=<github login> GHCR_TOKEN=<token with read:packages> deploy/create-secrets.sh
#
# Secret hubra-env:             every KEY= in .env, DATABASE_URL pointed at the postgres Service
#                               (POSTGRES_HOST, default postgres; postgres-rw for CloudNativePG)
# Secret hubra-postgres:        if POSTGRES_HOST is set: owner + password for a CloudNativePG cluster
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
# Secret values go through files only readable by us, never as command-line
# arguments (other users on the host could read those in `ps`).
umask 077
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
env_out="$tmp/env"
sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' "$ENV_FILE" | sort -u | grep -vx DATABASE_URL |
  while read -r key; do printf '%s=%s\n' "$key" "$(printenv "$key" || true)"; done > "$env_out"
echo "DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}/$POSTGRES_DB" >> "$env_out"
apply create secret generic hubra-env --from-env-file="$env_out"

if [ -n "${POSTGRES_HOST:-}" ]; then
  printf '%s' "$POSTGRES_USER" > "$tmp/username"
  printf '%s' "$POSTGRES_PASSWORD" > "$tmp/password"
  apply create secret generic hubra-postgres --type=kubernetes.io/basic-auth \
    --from-file=username="$tmp/username" --from-file=password="$tmp/password"
fi

if [ -n "${GHCR_USER:-}" ]; then
  auth="$(printf '%s:%s' "$GHCR_USER" "$GHCR_TOKEN" | base64 | tr -d '\n')"
  printf '{"auths":{"ghcr.io":{"username":"%s","auth":"%s"}}}' "$GHCR_USER" "$auth" \
    > "$tmp/dockerconfig"
  apply create secret generic ghcr-pull --type=kubernetes.io/dockerconfigjson \
    --from-file=.dockerconfigjson="$tmp/dockerconfig"
fi

if [ -f "$ROOT/modules/mail/certbot/cloudflare.ini" ]; then
  apply create secret generic cloudflare-credentials \
    --from-file=cloudflare.ini="$ROOT/modules/mail/certbot/cloudflare.ini"
fi
