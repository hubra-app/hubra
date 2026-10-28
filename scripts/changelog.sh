#!/bin/sh
# Release notes for a tag, from the commit subjects since the previous v* tag
# (Conventional Commits: feat, fix, ...). Used by the GitLab release job.
#
#   scripts/changelog.sh v1.2.0 > release-notes.md
set -eu

tag="${1:?usage: scripts/changelog.sh <tag>}"
prev="$(git describe --tags --abbrev=0 --match 'v[0-9]*' "$tag^" 2>/dev/null || true)"
range="${prev:+$prev..}$tag"

# section <title> <pattern> [-v]: the commits whose subject matches (-v: doesn't).
section() {
  title="$1" pattern="$2" invert="${3:-}"
  lines="$(git log --no-merges --format='%s (%h)' "$range" | grep -E ${invert:+"$invert"} "$pattern" || true)"
  [ -n "$lines" ] || return 0
  printf '### %s\n\n' "$title"
  # "feat(finance): add X (abc123)" -> "- **finance:** add X (abc123)";
  # other types keep their prefix ("- docs: ...").
  printf '%s\n' "$lines" | sed -E \
    -e 's/^(feat|fix|perf)\(([^)]+)\): /- **\2:** /' -e 't' \
    -e 's/^(feat|fix|perf): /- /' -e 't' \
    -e 's/^/- /'
  printf '\n'
}

if [ -n "$prev" ]; then
  printf '## Changes since %s\n\n' "$prev"
else
  printf '## Changes\n\n'
fi
section 'Breaking changes' '^[a-z]+(\([^)]+\))?!: '
section 'Features' '^feat(\([^)]+\))?: '
section 'Fixes' '^fix(\([^)]+\))?: '
section 'Performance' '^perf(\([^)]+\))?: '
section 'Other changes' '^([a-z]+(\([^)]+\))?!|(feat|fix|perf)(\([^)]+\))?): ' -v
