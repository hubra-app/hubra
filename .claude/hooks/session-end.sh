#!/usr/bin/env bash
# Stop hook: runs basic checks at session end.

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)

if [[ -z "$REPO_ROOT" ]]; then
  exit 0
fi

# Check for leftover debug statements in staged/modified JS/TS files
DIRTY_FILES=$(git -C "$REPO_ROOT" diff --name-only HEAD 2>/dev/null | grep -E '\.(js|ts|jsx|tsx)$' || true)

if [[ -n "$DIRTY_FILES" ]]; then
  DEBUG_HITS=$(echo "$DIRTY_FILES" | xargs grep -l 'console\.log\|debugger' 2>/dev/null || true)
  if [[ -n "$DEBUG_HITS" ]]; then
    echo "Warning: possible debug statements left in: $DEBUG_HITS" >&2
  fi
fi

exit 0
