#!/usr/bin/env bash
# Runs ruff on Python files written/edited by the agent.
# Reads the Claude Code tool response JSON from stdin.
set -euo pipefail

INPUT=$(cat 2>/dev/null || true)
if [[ -z "$INPUT" ]]; then
  exit 0
fi

FILE=$(printf '%s' "$INPUT" | jq -r '.tool_response.filePath // .tool_input.file_path // empty' 2>/dev/null || true)

if [[ -n "$FILE" && "$FILE" != "null" && "$FILE" =~ \.py$ ]]; then
  ruff check "$FILE" 2>/dev/null || true
fi
