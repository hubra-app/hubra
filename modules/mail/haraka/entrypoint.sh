#!/bin/sh
set -e

mkdir -p /app/config/

generate() {
  src="$1"
  dst="$2"

  for f in "${src}"/*; do
    [ -f "$f" ] || continue
    envsubst < "$f" > "${dst}/$(basename "${f%.template}")"
  done
}

generate /app/config.template            /app/config

exec node /usr/local/lib/node_modules/Haraka/bin/haraka -c /app
