# Release guidelines and image versions

Status: proposal. Nothing in the workflows changes until an option below is
picked. The release flow itself (release branches, checks) is in
[ci.md](ci.md).

## How images are versioned today

`images.yml` builds all seven images in one matrix, every time it runs:

| Image | Built from | Deployed by |
| --- | --- | --- |
| `backend` | `app/backend/` | Compose, k3s, Contabo |
| `frontend` (club app) | `app/frontend/`, `packages/`, `app/deploy/nginx/` | Compose, k3s, Contabo |
| `admin-frontend` (manage) | `app/admin-frontend/`, `packages/`, `app/deploy/nginx/` | Compose, k3s, Contabo |
| `sso-frontend` | `app/sso-frontend/`, `packages/`, `app/deploy/nginx/` | Compose, k3s, Contabo |
| `haraka`, `zonemta`, `cert-watcher` | `modules/mail/<name>/` | mail module only (suspended by default) |

- It runs when a GitHub release is published, or by hand. Pushes to `main`
  build nothing (to save minutes, PR #31).
- Every build gets `sha-<commit>`. Releases add `1.2.3`, `1.2` and `latest`;
  manual runs on `main` add `main-<timestamp>-<commit>`.
- Every image carries the same tag and the same `GIT_SHA`, even when its
  code did not change. The SSO image built for a backend-only fix is a new
  image with a new digest and the same content.
- Deploys pin one tag for all four app images: `HUBRA_VERSION` in Compose,
  `newTag: latest` in `deploy/app`, `newTag: sha-<commit>` in
  `deploy/clusters/contabo`. So every deploy restarts every pod.
- No GitHub release has been published yet. `CHANGELOG.md` has only
  `[Unreleased]`, so Contabo runs manual `sha-` builds.

## The problem

1. **Unchanged images are rebuilt and restarted.** Since 2026-10-28, 83 pull
   requests were merged into `main`. The SSO image's inputs changed in 30 of
   them, manage in 43, the club app in 46, the backend in 63, the mail
   images in 1. Each manual build still rebuilt and redeployed all seven.
2. **The tag does not say what changed.** `sha-abc123` on the SSO image
   does not tell you whether SSO changed since the last deploy.
3. **No versions yet.** Without releases there is no version to name in a
   support message, a changelog entry, or a rollback.

Actions minutes are a smaller issue than before: the repository is public,
so standard runners are free. A full Images run is about 12 runner minutes
(seven parallel jobs plus Trivy), and the release checks before it cost
more than the builds.

## Options

### A. One version, build only what changed (recommended)

Hubra keeps one version number for the whole product (`v1.4.0`). When
Images runs, each image compares its input paths (table above, plus its
Dockerfile and `images.yml`) with the commit of its last published build:

- **Changed:** build, scan and push, as today.
- **Unchanged:** no build. The previous image gets the new tags
  (`1.4.0`, `1.4`, `latest`, `sha-<commit>`) with
  `docker buildx imagetools create`, which copies the tag in the registry
  and keeps the digest.

The last build's commit comes from the image label
`org.opencontainers.image.revision`, which `metadata-action` already sets.
If it is missing or unreadable, the image is built: when in doubt, build.

Deploys keep naming one version, but **pin by digest**. Kubernetes restarts a
pod when its image string changes, even if the digest is the same, so an
overlay with `newTag: 1.4.0` would still restart SSO. The GitLab Release
already lists the digests; Contabo would use `digest:` instead of
`newTag:`, and unchanged images keep their digest and their pods.

- Deploy risk: low. One version still means "these four images were tested
  together" (release checks run on the release commit with all four). A
  wrong path list is the only new risk: a missed path means a stale image.
  `packages/` and `app/deploy/nginx/` count for all three frontends, and a
  manual run can force a full build (`build_all: true`).
- Minutes: a backend-only patch release builds one image instead of seven.
  Over a normal release most app images change anyway, so the saving is
  mostly the mail images and patch releases.
- The build badge and manage › Diagnose › Builds show the commit each image
  was built from, so an unchanged SSO shows an older commit. That is
  correct, and Builds should show the release version next to it.
- Work: one `changes` step in `images.yml` (like the one in `ci.yml`), a
  retag step, a `build_all` input, and digest pins in the Contabo overlay
  and the docs. About half a day.

### B. A version per image

Each image gets its own version and tag (`sso-frontend 1.3.2`,
`backend 2.1.0`), released when it changes, with its own changelog section.

- Deploy risk: medium. A frontend can now meet a backend it was never
  tested with. That needs an API compatibility rule (the backend keeps
  older endpoints for N versions) and a matrix of which versions work
  together, which the release checks would also have to test.
- Minutes: the same as A.
- Cost to people: what's new, support and the GitLab Releases would have to
  speak in four versions. For one maintainer and one platform, this adds
  bookkeeping and no safety. Worth it only when outside installs upgrade
  parts separately.

### C. Split into separate modules or repositories

The SSO portal, manage and the club app move to their own repositories (or
a monorepo with independent packages) with their own CI and releases.

- Deploy risk: highest. The shared `packages/api-client` and `packages/ui`
  would need to be published and versioned, and a change that touches the
  backend and a frontend becomes two coordinated releases.
- Minutes: lowest per change, but more CI to maintain.
- Fits a team per app. Hubra is one codebase where most features touch the
  backend and at least one frontend (63 of 83 merges touched the backend).

## Recommendation

**Option A**, plus the release habit below. It answers "why rebuild SSO when
nothing changed" without giving up the single version that makes deploys,
rollbacks and the changelog simple. Options B and C solve problems Hubra
does not have yet; A does not block moving to B later.

## Release guidelines (all options)

- **Version numbers:** semver for the product. Minor (`1.4.0`) for features
  and migrations, patch (`1.4.1`) for fixes without migrations. A release
  with a migration that needs a manual step says so at the top of its notes.
- **Cadence:** cut a release when a batch of features is done, roughly
  weekly, rather than deploying manual `main` builds. Manual builds stay
  for testing a fix before it goes into a release.
- **Flow:** `release/1.4` from `main`, fixes via pull requests into it (and
  back into `main`), then publish GitHub release `v1.4.0` on the branch
  ([ci.md](ci.md)). Patch releases come from the same branch.
- **Changelog:** move `[Unreleased]` in `CHANGELOG.md` and
  `CHANGELOG.de.md` to the new version in the release pull request, so
  what's new matches the deployed version.
- **Deploy:** production names a release, never `latest` or a `main-`
  build. Roll back by pinning the previous release.
