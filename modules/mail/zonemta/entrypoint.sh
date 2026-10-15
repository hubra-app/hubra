#!/bin/sh
set -e

mkdir -p /app/config/interfaces /app/config/plugins /app/config/zones

generate() {
  src="$1"
  dst="$2"

  for f in "${src}"/*.toml; do
    [ -f "$f" ] || continue
    envsubst < "$f" > "${dst}/$(basename "${f%.template}")"
  done
}

generate /app/config.template            /app/config
generate /app/config.template/interfaces /app/config/interfaces
generate /app/config.template/plugins    /app/config/plugins
generate /app/config.template/zones      /app/config/zones

exec node index.js "$@"
