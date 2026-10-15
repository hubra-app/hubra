#!/bin/sh
set -eu

TRIGGER_DIR="/run/mail-reload"
mkdir -p "$TRIGGER_DIR"

date +%s > "$TRIGGER_DIR/wildduck.reload"
date +%s > "$TRIGGER_DIR/haraka.reload"

echo "certbot deploy hook: wrote reload triggers for WildDuck and Haraka"
