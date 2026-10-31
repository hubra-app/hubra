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

# Backups are encrypted to an age public key; its private key is printed
# once below and never written to the file.
backup_private=""
backup_public=""
if command -v age-keygen >/dev/null 2>&1; then
  backup_private="$(age-keygen 2>/dev/null | grep '^AGE-SECRET-KEY-')"
  backup_public="$(printf '%s\n' "$backup_private" | age-keygen -y)"
fi
fernet() { head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n'; }

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    SECRET_KEY= | JWT_SECRET_KEY= | POSTGRES_PASSWORD= | REDIS_PASSWORD= | \
    MONGO_PASSWORD= | WILDDUCK_API_TOKEN= | LOOP_SECRET= | SRS_SECRET= | \
    API_BOT_KEY= | BACKUP_ENCRYPTION_KEY=)
      printf '%s%s\n' "$line" "$(hex)" ;;
    FERNET_KEY=)
      printf '%s%s\n' "$line" "$(fernet)" ;;
    BACKUP_PUBLIC_KEY=)
      printf '%s%s\n' "$line" "$backup_public" ;;
    *)
      printf '%s\n' "$line" ;;
  esac
done < .env.example > "$out"

chmod 600 "$out"
echo "Wrote $out with fresh secrets. Keep FERNET_KEY in a password manager."
if [ -n "$backup_private" ]; then
  echo
  echo "Backup private key (shown once, not saved anywhere; put it in a password"
  echo "manager now, restores need it):"
  echo "  $backup_private"
else
  echo "age-keygen is not installed: BACKUP_PUBLIC_KEY is empty, so backups use"
  echo "the BACKUP_ENCRYPTION_KEY passphrase. Run \`flask backups keygen\` later to switch."
fi
