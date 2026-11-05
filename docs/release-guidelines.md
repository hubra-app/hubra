# Release guidelines and image versions

Hubra has one version for the whole product (`v1.4.0`), and every image
carries it. An image is only rebuilt when its own files changed. The release
flow itself (release branches, checks) is in [ci.md](ci.md).

## Images and what goes into them

`images.yml` handles every image. Each has a list of paths (a backend role
image: its role's file list, `app/backend/scripts/role_files.py`): a change in one
of them (or in `.dockerignore`, or in how `images.yml` builds that image: its
matrix entry and the build step) means a new build. Other edits to
`images.yml` (comments, tags, scans, other jobs) rebuild nothing.

| Image | Paths | Deployed by |
| --- | --- | --- |
| `backend` | `app/backend/` | Compose, k3s, Contabo |
| `frontend` (club app) | `app/frontend/`, `packages/`, `app/deploy/nginx/` | Compose, k3s, Contabo |
| `admin-frontend` (manage) | `app/admin-frontend/`, `packages/`, `app/deploy/nginx/` | Compose, k3s, Contabo |
| `sso-frontend` | `app/sso-frontend/`, `packages/`, `app/deploy/nginx/` | Compose, k3s, Contabo |
| `haraka`, `zonemta`, `cert-watcher` | `modules/mail/<name>/` | mail module only (suspended by default) |

When a Dockerfile starts copying something new, add that path to the
image's `paths` in `images.yml`, or that image can go stale.

## How a run decides

Images runs for a release (called by `release.yml` when a `v*` tag is pushed),
or by hand (Actions > Images > Run workflow). The full release checks run first, on the whole
commit, with every image built from source. Then, per image,
`scripts/image-reuse.sh` reads the image's `last-build` tag on GHCR and the
commit it was built from (the `org.opencontainers.image.revision` label):

- **Files changed since then:** build, push and scan, as before. Text files
  (Markdown, `README`, `.gitignore`) do not count, except `CHANGELOG.md` and
  `CHANGELOG.de.md`, which the backend image serves as "What's new".
- **Unchanged:** no build. The last build gets this run's tags with
  `docker buildx imagetools create`, which copies tags in the registry and
  keeps the digest. Trivy still scans it.
- **When in doubt, build:** no earlier build, no label, a commit missing
  from the history, or "Build every image" ticked on a manual run.

Each job's summary says built or reused and why. The run ends with a
`digests` job that writes an `images:` block with every image pinned by
digest.

A reused image keeps its build commit: manage › Diagnose › Builds and the
build badge show the commit the image was built from, which can be older
than the release.

## Tags

| Tag | On |
| --- | --- |
| `1.2.3` | release `v1.2.3`, once approved (pre-releases too) |
| `1.2` | release `v1.2.3`, once approved, not pre-releases |
| `latest` | the newest build: approved releases (not pre-releases) and manual runs on `main` |
| `sha-<commit>` | every run |
| `main-<timestamp>-<commit>` | manual runs on `main`, for Flux image automation |
| `last-build` | every run; how the next run finds this image's last build (not for deploys) |

All the images get every tag of a run, built or reused, so one version
always names a full set that passed the release checks together.

## Deploying

- **k3s / Contabo:** paste the "Images pinned by digest" block from the
  Images run summary (or the GitLab Release notes) over the overlay's
  `images:`. Kubernetes restarts a pod when its image string changes, so
  with a bare `newTag: 1.4.0` every pod restarts. With the digest, the
  unchanged images keep their digest and their pods keep running.
- **Compose:** set `HUBRA_VERSION` and run `docker compose pull && docker
  compose up -d`. Compose only recreates containers whose image changed, so
  reused images are left alone.
- Production names a release (or, between releases, a `sha-` build), never
  `latest`. Roll back by pinning the previous block.

## Release guidelines

- **Version numbers:** semver for the product. Minor (`1.4.0`) for features
  and migrations, patch (`1.4.1`) for fixes without migrations. A release
  with a migration that needs a manual step says so at the top of its notes.
- **Cadence:** cut a release when a batch of features is done, roughly
  weekly, rather than deploying manual `main` builds. Manual builds stay
  for trying a fix before it goes into a release.
- **Flow:** push tag `v1.4.0` on `main` ([releases.md](releases.md));
  the Release workflow runs the full checks and builds the images, waits for
  a maintainer's approval, then tags and signs the images, publishes the
  GitHub release and creates `release/1.4` there (one per minor version,
  never per patch; pre-releases create none). Patch releases (`1.4.1`,
  `1.4.2`) are tagged on that branch, and each fix is merged back into
  `main`. To stabilize before `v1.4.0` while `main` moves on, create
  `release/1.4` by hand first and tag there; the workflow leaves an existing
  branch alone ([ci.md](ci.md)).
- **Version and changelog:** in a pull request just before tagging, set
  `version` in `app/backend/pyproject.toml` (the tag must match it) and move `[Unreleased]` in
  `CHANGELOG.md` and `CHANGELOG.de.md` to the new version, so what's new
  matches the deployed version.

## Options considered (2026-11-02)

Before this, every run rebuilt all seven images with the same tag, and every
deploy restarted every pod. Since 2026-10-28 the SSO image's files changed
in 30 of 83 merged pull requests, the mail images in 1.

- **A. One version, build only what changed** (chosen). Keeps one version
  for deploys, rollbacks and the changelog. The new risk is a wrong path
  list leaving an image stale, hence "when in doubt, build" and the
  "Build every image" switch.
- **B. A version per image** (`sso-frontend 1.3.2`, `backend 2.1.0`). A
  frontend could meet a backend it was never tested with, so it needs an API
  compatibility rule and a test matrix, and what's new and support would
  speak in four versions. Worth it only once outside installs upgrade parts
  separately.
- **C. Separate repositories per app.** `packages/api-client` and
  `packages/ui` would need publishing, and most features (63 of 83 merges
  touched the backend) would become two coordinated releases.

Actions minutes were a minor factor: the repository is public, so standard
runners are free. A full Images run is about 12 runner minutes; a
backend-only patch release now builds only the backend images it touches.
