# Releasing Hubra

Hubra releases the way the plugins do: push a version tag, and
`.github/workflows/release.yml` tests it, builds the images, waits for a
maintainer's approval and only then publishes the release. Versions, tags
and which images get rebuilt are in [release-guidelines.md](release-guidelines.md);
the checks themselves in [ci.md](ci.md).

## Cutting a release

1. In a pull request, set `version` in `app/backend/pyproject.toml` to the
   new version and move `[Unreleased]` in `app/backend/CHANGELOG.md` and
   `CHANGELOG.de.md` to `## [1.3.0] - <date>`. Merge it.
2. Tag the merge commit on `main` (or on `release/1.3` for a patch) and push
   the tag:

   ```sh
   git tag v1.3.0 && git push origin v1.3.0
   # or with the hubra command: hubra release hubra
   ```

3. Wait for the run (Actions > Release). When the images are built it
   stops at **approve**: open the run, check the digest block of the Images
   job summary, then **Review deployments > release > Approve**. Reject to
   stop; nothing called 1.3.0 exists yet, so tag a new version after the fix.
4. The run then tags and signs the images, publishes the GitHub release
   (notes from the changelog, the digest block, `images.yaml`, `images.txt`,
   `SHA256SUMS`), creates `release/1.3` if it is missing and mirrors the tag
   to GitLab.

A pre-release (`v1.3.0-rc.1`) runs the same way, but gets no `1.3` or
`latest` tag and no release branch, and needs no changelog section.

To write the release text yourself, create a **draft** release for the tag
before pushing it; the run fills it in and publishes it, keeping your text
on top. A published release is never changed: release a new version.

## What the run checks

| Job | What happens |
| --- | --- |
| `check` | the tag is `vX.Y.Z` (or `-rc.N`) and matches `pyproject.toml`; the changelog has that section; the commit is on `main` or a `release/*` branch; the release is not published yet |
| `images` | `images.yml`: all of `release-checks.yml` (every test, Postgres, audits, browser tests), then the images, pushed as `sha-<commit>` and `last-build` only. A new build gets a provenance attestation. |
| `approve` | environment `release`: waits for a required reviewer |
| `promote` | the same digests get `1.3.0`, `1.3` and `latest`; each image is signed with cosign |
| `release` | the GitHub release, created with its files (immutable releases take no files later) |
| `branch` | `release-branch.yml`: `release/1.3` at the tag, if it does not exist |
| `mirror` | `mirror-gitlab.yml`: the tag to GitLab, which creates the GitLab Release |

The approval comes after the build on purpose: you approve the exact
digests that passed the checks, and promoting them takes seconds.

A release created by a workflow starts no other workflows, so the release
branch and the mirror are called from `release.yml`, and "Publish release"
in the GitHub UI is not the way to release any more (it would create the
tag, start this workflow and then fail, because the release would already be
published). Use the tag push.

## Signing

Two signatures per image, both keyless (Sigstore, with the run's GitHub
OIDC token), so there is no private key to store or rotate:

- **Build provenance** (`images.yml`, when an image is built): which
  repository, commit and workflow run built this digest. A reused image
  keeps the attestation of the run that built it.
- **Release signature** (`release.yml`, after the approval): "the release
  workflow of `hubra-app/hubra`, run for tag `v1.3.0`, published this digest",
  with the annotations `version` and `commit`.

The plugins use an Ed25519 key instead because Hubra servers verify plugins
themselves when they install them. Nothing installs Hubra core that way:
Docker, Compose and Flux pull images by digest, and the digest in a pinned
overlay already fixes the content. The signatures let anyone check that a
digest came from this repository's release workflow.

Verify an image:

```sh
img=ghcr.io/hubra-app/hubra/backend@sha256:...   # from images.yaml

cosign verify "$img" \
  --certificate-identity-regexp '^https://github.com/hubra-app/hubra/\.github/workflows/release\.yml@refs/tags/v' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

gh attestation verify "oci://$img" --repo hubra-app/hubra
```

And the release files: `sha256sum -c SHA256SUMS`.

## Setup (once)

In Settings of `hubra-app/hubra`:

1. **Environments > New environment `release`.** Required reviewers: the
   maintainers who approve releases. Leave "Prevent self-review" off (the
   person who pushes the tag approves it). Deployment branches and tags:
   **Selected branches and tags**, add the tag rule `v*`. Without this
   environment the approve job runs unprotected, so create it before the
   first tag.
2. **General > Releases > Enable release immutability**, so a published
   release and its files can never be swapped.
3. The `v*` tag ruleset (`.github/rulesets/tags.json`) already keeps tags
   from being moved or deleted.
