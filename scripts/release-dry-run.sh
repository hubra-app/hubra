#!/usr/bin/env bash
# Runs the release workflow's checks and notes (scripts/release_check.py) for
# the version app/backend/pyproject.toml declares, without a tag: what
# `git tag v<version>` would run into. Used by ci.yml (release-check) and
# release-dry-run.yml; works locally too:  scripts/release-dry-run.sh
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(python3 -c 'import tomllib; print(tomllib.load(open("app/backend/pyproject.toml", "rb"))["project"]["version"])')
tag="v$version"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
echo "== check $tag"
GITHUB_OUTPUT="" python3 scripts/release_check.py check "$tag"
# Placeholder images: the real block comes from the promote job.
printf 'images:\n  - name: ghcr.io/example/backend\n    newTag: "%s"\n    digest: sha256:0\n' "$version" > "$tmp/images.yaml"
echo "== notes $tag"
python3 scripts/release_check.py notes "$tag" --images "$tmp/images.yaml" --out "$tmp/out" --notes "$tmp/notes.md"
cat "$tmp/notes.md"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  { echo "### Release notes for $tag (dry run)"; echo; cat "$tmp/notes.md"; } >> "$GITHUB_STEP_SUMMARY"
fi
