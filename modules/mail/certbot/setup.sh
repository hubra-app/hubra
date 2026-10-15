#!/bin/sh
set -eu

CREDENTIALS_FILE="${1:-mail/certbot/cloudflare.ini}"

if [ ! -f "$CREDENTIALS_FILE" ]; then
  echo "missing credentials file: $CREDENTIALS_FILE" >&2
  exit 1
fi

if command -v stat >/dev/null 2>&1; then
  perms="$(stat -c '%a' "$CREDENTIALS_FILE" 2>/dev/null || true)"
  if [ "$perms" != "600" ]; then
    echo "expected 600 permissions for $CREDENTIALS_FILE, got ${perms:-unknown}" >&2
    echo "fix with: chmod 600 $CREDENTIALS_FILE" >&2
    exit 1
  fi
fi

echo "$CREDENTIALS_FILE permission check passed"
