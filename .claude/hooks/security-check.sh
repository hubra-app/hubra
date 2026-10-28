#!/usr/bin/env bash
# PreToolUse hook: blocks dangerous bash patterns before execution.
# Reads the Claude Code tool input JSON from stdin.

COMMAND=$(cat | jq -r '.tool_input.command // ""' 2>/dev/null)

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# Block piping directly into a shell interpreter
if echo "$COMMAND" | grep -qE '\|\s*(bash|sh|zsh|fish)\s*(-[a-z]+\s*)?$'; then
  echo "BLOCKED: Piping into a shell interpreter is not allowed: $COMMAND" >&2
  exit 2
fi

# Block destructive disk/system operations
if echo "$COMMAND" | grep -qE '(rm\s+-rf\s+/[^a-z]|mkfs\s|fdisk\s|dd\s+if=.+of=/dev/(sd|hd|nvme|disk)|:()\{.*\|.*\&.*\})'; then
  echo "BLOCKED: Destructive system operation detected: $COMMAND" >&2
  exit 2
fi

exit 0
