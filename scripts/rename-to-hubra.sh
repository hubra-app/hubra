#!/usr/bin/env bash
# Rename the backend Python package vollbuild -> hubra.
#
# Moves app/backend/vollbuild to app/backend/hubra and rewrites every
# reference to the package (imports, mock.patch targets, Celery task names,
# module manifests, gunicorn/celery entry points, tooling config) and the
# frontends' @vollbuild/api-client import alias. The
# vollbuild.ch hosts and vollbuild.die-ganz-witzige.ch are left alone.
#
# Idempotent: run it again on a branch that still has vollbuild.* imports
# (e.g. after rebasing older work onto the rename) and it converts the rest.
#
# Usage: scripts/rename-to-hubra.sh   (from anywhere inside the repo)
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [ -d app/backend/vollbuild ]; then
  if [ -d app/backend/hubra ]; then
    # Both exist (new files added under the old path): move them across.
    (cd app/backend/vollbuild && git ls-files -z) |
      while IFS= read -r -d '' f; do
        mkdir -p "app/backend/hubra/$(dirname "$f")"
        git mv -k "app/backend/vollbuild/$f" "app/backend/hubra/$f"
      done
    find app/backend/vollbuild -depth -type d -empty -delete
  else
    git mv app/backend/vollbuild app/backend/hubra
  fi
fi

# Historical notes and local tool config keep the old paths.
git ls-files -z -- . \
  ':!graphify-out' ':!docs/prompts' ':!.claude' \
  ':!SECURITY-AUDIT.md' ':!app/backend/CHANGELOG.md' \
  ':!scripts/rename-to-hubra.sh' |
  { xargs -0 grep -IlZ 'vollbuild' -- 2>/dev/null || true; } |
  xargs -0 -r perl -pi -e 's/\bvollbuild\b(?!\\*\.ch\b|\\*\.die-ganz)/hubra/g'

echo "Renamed. Left alone (should all be host names):"
git grep -n 'vollbuild' -- app deploy modules docker-compose*.y*ml pyrightconfig.json \
  .pre-commit-config.yaml ':!app/backend/CHANGELOG.md' | grep -v 'vollbuild\\*\.ch\|vollbuild\.die-ganz' || echo "  (nothing else)"
echo "The shorter name lets ruff join some lines: run ruff format on the changed backend files."
