#!/bin/sh
# Create the secrets that stay out of git. Run once per cluster, and again after
# changing .env (then `kubectl -n club rollout restart deployment`).
#
#   REGISTRY_USER=... REGISTRY_PASSWORD=... deploy/create-secrets.sh
#
# Secret club-env:              every KEY= in .env, DATABASE_URL pointed at the postgres Service
# Secret gitlab-registry:       if REGISTRY_USER/REGISTRY_PASSWORD are set (deploy token, read_registry)
# Secret cloudflare-credentials: if modules/mail/certbot/cloudflare.ini exists (mail module)
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
NS=club

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
apply create secret generic club-env --from-env-file="$env_out"

if [ -n "${REGISTRY_USER:-}" ]; then
  apply create secret docker-registry gitlab-registry --docker-server=registry.gitlab.com \
    --docker-username="$REGISTRY_USER" --docker-password="$REGISTRY_PASSWORD"
fi

if [ -f "$ROOT/modules/mail/certbot/cloudflare.ini" ]; then
  apply create secret generic cloudflare-credentials \
    --from-file=cloudflare.ini="$ROOT/modules/mail/certbot/cloudflare.ini"
fi
