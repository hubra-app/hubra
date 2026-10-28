#!/bin/sh
set -eu

# Testing notes:
# To manually test without waiting for certbot:
#   docker exec community-cert-watcher touch /etc/letsencrypt/live/mail.hubra.club/fullchain.pem
#   # should trigger restart of community-mailserver, community-haraka, community-zonemta
#
# To simulate symlink recreation (closer to what certbot does):
#   docker exec community-cert-watcher sh -c '
#     cd /etc/letsencrypt/live/mail.hubra.club &&
#     ln -sf "$(readlink fullchain.pem)" fullchain.pem.tmp &&
#     mv fullchain.pem.tmp fullchain.pem'
#
# To verify polling fallback works without inotify:
#   docker exec community-cert-watcher pkill inotifywait
#   # then touch a cert file and wait POLL_INTERVAL seconds
#
# To verify socket-proxy blocks exec:
#   docker exec community-cert-watcher docker exec community-mailserver echo hi
#   # should fail with 403 from socket-proxy
#
# To verify the allow-list validation:
#   # Temporarily set RESTART_CONTAINERS to an unlisted name in compose and
#   # run `docker compose up cert-watcher` — it should exit 1 immediately.

ALLOWED_CONTAINERS="${ALLOWED_CONTAINERS:-}"
RESTART_CONTAINERS="${RESTART_CONTAINERS:-}"
WATCH_DIR="${WATCH_DIR:-/etc/letsencrypt}"
MAIL_HOST="${MAIL_HOST:-}"
SETTLE_SECONDS="${SETTLE_SECONDS:-3}"
POLL_INTERVAL="${POLL_INTERVAL:-300}"
LAST_RESTART_EPOCH=0

log() {
  printf '%s cert-watcher: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*"
}

is_allowed() {
  candidate="$1"
  for allowed in $ALLOWED_CONTAINERS; do
    if [ "$allowed" = "$candidate" ]; then
      return 0
    fi
  done
  return 1
}

# Fail fast on misconfiguration before watcher starts.
for container in $RESTART_CONTAINERS; do
  if ! is_allowed "$container"; then
    log "ERROR startup validation failed: '$container' is not in ALLOWED_CONTAINERS"
    exit 1
  fi
done

while [ ! -d "$WATCH_DIR" ]; do
  log "waiting for WATCH_DIR to exist: $WATCH_DIR"
  sleep 5
done

# --- Trigger pipe ---
# Both inotify and polling write trigger lines to this FIFO.
# The foreground reader processes them with dedupe + settle.
TRIGGER_PIPE="/tmp/cert-reload-trigger"
rm -f "$TRIGGER_PIPE"
mkfifo "$TRIGGER_PIPE"
exec 3<>"$TRIGGER_PIPE"

do_restart() {
  reason="$1"
  sleep "$SETTLE_SECONDS"

  now_epoch="$(date +%s)"
  elapsed=$((now_epoch - LAST_RESTART_EPOCH))
  if [ "$elapsed" -lt 60 ]; then
    log "skipping restart cycle due to dedupe window (${elapsed}s < 60s) — trigger: $reason"
    return
  fi

  LAST_RESTART_EPOCH="$now_epoch"

  for container in $RESTART_CONTAINERS; do
    if ! is_allowed "$container"; then
      log "SKIP container '$container': not in ALLOWED_CONTAINERS"
      continue
    fi

    if docker restart "$container" >/dev/null 2>&1; then
      log "restart succeeded for '$container' — trigger: $reason"
    else
      log "ERROR restart failed for '$container' — trigger: $reason"
    fi
  done
}

# --- inotify watcher (background) ---
# Watches /etc/letsencrypt recursively for .pem file changes.
# Events cover both archive/ file writes (close_write) and
# live/ symlink updates (create, delete, attrib, moved_to).
(
  if command -v inotifywait >/dev/null 2>&1; then
    log "inotify: starting recursive watch on $WATCH_DIR"
    inotifywait -m -r \
      -e close_write -e moved_to -e create -e delete -e attrib \
      "$WATCH_DIR" | while read -r dir events file; do
        case "$file" in
          *.pem)
            printf 'inotify %s %s%s\n' "$events" "$dir" "$file" >&3
            ;;
        esac
      done
    log "WARNING inotifywait process exited — polling fallback still active"
  else
    log "WARNING inotifywait not found — relying on polling fallback only"
  fi
) &
INOTIFY_PID=$!

# --- polling fallback (background) ---
# Every POLL_INTERVAL seconds, resolves cert symlinks via readlink -f
# and checks the target file mtime. Catches renewals that inotify
# misses (e.g. cross-container inotify event gaps on some storage drivers).
(
  last_hash=""
  cycle=0
  while true; do
    sleep "$POLL_INTERVAL"
    cycle=$((cycle + 1))

    cert_dir="/etc/letsencrypt/live/${MAIL_HOST}"
    if [ -z "$MAIL_HOST" ] || [ ! -d "$cert_dir" ]; then
      continue
    fi

    current_hash=""
    for f in "$cert_dir"/fullchain.pem "$cert_dir"/privkey.pem; do
      resolved=$(readlink -f "$f" 2>/dev/null || echo "")
      if [ -n "$resolved" ] && [ -f "$resolved" ]; then
        m=$(stat -c '%Y' "$resolved" 2>/dev/null || echo "0")
      else
        m="missing"
      fi
      current_hash="${current_hash}${m}:"
    done

    if [ -n "$last_hash" ] && [ "$current_hash" != "$last_hash" ]; then
      printf 'poll mtime-changed %s\n' "$current_hash" >&3
    fi
    last_hash="$current_hash"

    # Heartbeat every ~1 hour (12 cycles at 300s)
    if [ $((cycle % 12)) -eq 0 ]; then
      log "poll heartbeat: cycle=$cycle cert_hash=$current_hash"
    fi
  done
) &
POLL_PID=$!

trap 'kill $INOTIFY_PID $POLL_PID 2>/dev/null || true; exit' TERM INT

log "cert-watcher started: inotify_pid=$INOTIFY_PID poll_pid=$POLL_PID interval=${POLL_INTERVAL}s watch=$WATCH_DIR"

# --- foreground: process triggers from FIFO ---
while read -r trigger_line <&3; do
  log "trigger received: $trigger_line"
  do_restart "$trigger_line"
done

log "ERROR trigger pipe closed — cert-watcher exiting"
