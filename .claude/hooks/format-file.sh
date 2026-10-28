#!/usr/bin/env bash
# Runs prettier on the file written/edited by the agent.
# Reads the Claude Code tool response JSON from stdin.
set -euo pipefail

INPUT=$(cat 2>/dev/null || true)
if [[ -z "$INPUT" ]]; then
  exit 0
fi

FILE=$(printf '%s' "$INPUT" | node -e \
  'const d=JSON.parse(require("fs").readFileSync(0,"utf-8"));
   const p=d.tool_response?.filePath||d.tool_input?.file_path;
   if(p&&/\.(js|ts|jsx|tsx|json|md|css|scss|html|vue)$/.test(p))process.stdout.write(p);
' 2>/dev/null || true)

if [[ -n "$FILE" ]]; then
  npx --yes prettier --write "$FILE" 2>/dev/null || true
fi
