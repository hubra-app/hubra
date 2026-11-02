#!/usr/bin/env bash
# Decides whether images.yml must build an image or can reuse its last build.
#
#   scripts/image-reuse.sh <image> <path>...
#
# <image> is the repository without a tag (ghcr.io/hubra-app/hubra/sso-frontend).
# Its `last-build` tag is the newest build of that image. <path>... are the
# files that go into the image: its build context, Dockerfile and shared code.
#
# The image is reused when none of those paths (nor .dockerignore or
# images.yml) changed between the commit the last build was made from (its
# org.opencontainers.image.revision label) and HEAD. Text files (Markdown
# other than the changelogs, README, .gitignore) do not count. git diff
# compares file contents, so the two commits may be on different branches. When in doubt
# (no earlier build, no label, commit not in this history, BUILD_ALL=true)
# the answer is build.
#
# Prints key=value lines for $GITHUB_OUTPUT:
#   build=true|false
#   digest=sha256:...   the image to retag (build=false only)
#   from=<commit>       the commit it was built from (build=false only)
#   reason=...          one line for the job summary
set -euo pipefail

image="${1:?usage: scripts/image-reuse.sh <image> <path>...}"
shift
[ "$#" -gt 0 ] || { echo "no paths given for $image" >&2; exit 2; }
paths=("$@" .dockerignore .github/workflows/images.yml)

build() { printf 'build=true\nreason=%s\n' "$1"; exit 0; }

[ "${BUILD_ALL:-false}" = true ] && build "build_all was set"

# Pin the digest first, then read that exact image, so a build pushed in
# between cannot mix the two.
digest="$(docker buildx imagetools inspect "$image:last-build" --format '{{json .Manifest}}' 2>/dev/null | jq -r '.digest // empty')" || true
[ -n "$digest" ] || build "no earlier build ($image:last-build not found)"

from="$(docker buildx imagetools inspect "$image@$digest" --format '{{json .Image}}' 2>/dev/null |
  jq -r 'if has("config") then . else (.["linux/amd64"] // (to_entries[0].value)) end
         | .config.Labels["org.opencontainers.image.revision"] // empty')" || true
[ -n "$from" ] || build "the last build has no revision label"

git cat-file -e "$from^{commit}" 2>/dev/null || build "commit ${from:0:7} of the last build is not in this history"

# Text files (Markdown, README, .gitignore) need no new image. The changelogs
# are the exception: the backend image serves them as "What's new".
changed="$(git diff --name-only "$from" HEAD -- "${paths[@]}" |
  awk -F/ '$NF ~ /^CHANGELOG.*\.md$/ || ($NF !~ /\.md$/ && $NF != "README" && $NF != ".gitignore")')"
if [ -n "$changed" ]; then
  build "changed since ${from:0:7}: $(echo "$changed" | head -n 5 | paste -sd ' ' -)"
fi

printf 'build=false\ndigest=%s\nfrom=%s\nreason=%s\n' "$digest" "$from" "unchanged since ${from:0:7}, reusing that image"
