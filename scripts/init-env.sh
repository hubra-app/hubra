#!/bin/sh
# Create .env from .env.example and fill every empty secret with a random
# value. Never overwrites an existing .env.
#
#   scripts/init-env.sh            # writes ./.env
#   scripts/init-env.sh other.env  # writes other.env
set -eu

cd "$(dirname "$0")/.."
out="${1:-.env}"

if [ -e "$out" ]; then
  echo "$out already exists; not touching it." >&2
  exit 1
fi

hex() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }
fernet() { head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n'; }

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    SECRET_KEY= | JWT_SECRET_KEY= | POSTGRES_PASSWORD= | REDIS_PASSWORD= | \
    MONGO_PASSWORD= | WILDDUCK_API_TOKEN= | LOOP_SECRET= | SRS_SECRET= | \
    API_BOT_KEY= | BACKUP_ENCRYPTION_KEY=)
      printf '%s%s\n' "$line" "$(hex)" ;;
    FERNET_KEY=)
      printf '%s%s\n' "$line" "$(fernet)" ;;
    *)
      printf '%s\n' "$line" ;;
  esac
done < .env.example > "$out"

chmod 600 "$out"
echo "Wrote $out with fresh secrets. Keep BACKUP_ENCRYPTION_KEY in a password manager."
