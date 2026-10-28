# Releases on GitLab

GitHub (`hubra-app/hubra`) stays the place for code, pull requests, their
checks, releases and the container images (GHCR). A GitLab project gets a
copy of `main` and the tags, runs the checks again and turns version tags into
GitLab Releases:

```
GitHub main ───────────────── mirror-gitlab.yml ──▶ GitLab main ──▶ checks
GitHub release v1.2.3 ┬─ images.yml ──▶ ghcr.io/hubra-app/hubra/<image>:1.2.3
 (creates tag v1.2.3) └─ mirror-gitlab.yml ──▶ GitLab tag ──▶ checks ─▶ GitLab Release
```

| Pipeline on GitLab | Jobs |
| --- | --- |
| `main`, merge requests | `backend` (ruff, pytest), `frontends` (lint, build, plugin frontends), `compose`, `kubernetes` (kustomize + kubeconform of every overlay), `shellcheck`, the same as `.github/workflows/ci.yml` |
| tag `v1.2.3` or `v1.2.3-rc.1` | the checks, then `release-notes` waits for GitHub to push the seven images of that version, looks up their digests, and `release` creates a GitLab Release with the changelog and the digests |

Only tags in semver form (`v` + `MAJOR.MINOR.PATCH`, optional `-pre.release`)
start a release. Any other tag runs nothing.

## Images

Every image is built once, by `.github/workflows/images.yml`, and lives at
`ghcr.io/hubra-app/hubra/<image>` (`backend`, `frontend`, `admin-frontend`,
`sso-frontend`, `haraka`, `zonemta`, `cert-watcher`):

| Tag | Pushed by |
| --- | --- |
| `1.2.3` | GitHub release `v1.2.3` (pre-releases too) |
| `1.2`, `latest` | GitHub release `v1.2.3`, not for pre-releases; `latest` not for the cluster |
| `sha-<commit>` | every build: releases and manual runs (Actions → Images → Run workflow) |

To save Actions minutes, a push to `main` builds no images.

The cluster pins a version, ideally by digest. Each GitLab Release ends with
an `images:` block for the overlay (`deploy/clusters/contabo/kustomization.yaml`)
with `newTag` and `digest` for every image. Paste it over the overlay's
`images:` and commit; Flux rolls out exactly those images and nothing else.
Between releases, run the Images workflow by hand on `main` and pin the
`sha-<commit>` build it pushes.

## Setup

1. **GitLab project.** Create an empty project, for example
   `<group>/hubra` (private). Settings → Repository → Protected tags:
   protect `v*` (allowed to create: Maintainers).
2. **Mirror token.** Settings → Access tokens → new project access token,
   role **Maintainer**, scope **write_repository**. Maintainer is needed to
   push to the protected `main` and the protected `v*` tags.
3. **GitHub.** In `hubra-app/hubra` → Settings → Secrets and variables →
   Actions:
   - variable `GITLAB_MIRROR_URL` = `gitlab.com/<group>/hubra.git`
     (no `https://`)
   - secret `GITLAB_MIRROR_TOKEN` = the token from step 2

   Then run **Mirror to GitLab** once from the Actions tab
   (workflow_dispatch). From then on every push to `main` and every `v*` tag
   reaches GitLab within a minute. With GitLab Premium, a pull mirror
   (Settings → Repository → Mirroring repositories) does the same job and the
   workflow can stay unconfigured.
4. **GHCR read access for GitLab.** The packages are private, so the release
   job needs a GitHub token (classic) with `read:packages` to look up the
   digests. Add it in GitLab under Settings → CI/CD → Variables (see below),
   masked and protected.

Any Docker runner works; nothing needs privileged mode.

## CI variables

| Where | Name | What |
| --- | --- | --- |
| GitHub, Actions variable | `GITLAB_MIRROR_URL` | GitLab repository path, `gitlab.com/<group>/hubra.git` |
| GitHub, Actions secret | `GITLAB_MIRROR_TOKEN` | GitLab project access token, Maintainer, `write_repository` |
| GitLab, CI/CD variable | `GHCR_USER` | GitHub login that owns `GHCR_TOKEN` |
| GitLab, CI/CD variable (masked, protected) | `GHCR_TOKEN` | GitHub token with `read:packages` |
| GitLab, CI/CD variable (optional) | `GHCR_WAIT_MINUTES` | How long the release waits for GitHub's images, default `30` |
| GitLab, CI/CD variable (optional) | `HUBRA_SKIP_MAIN_CHECKS` | `true` skips the pipeline on `main`, which GitHub already checked. Tags always run the checks. |

The release itself uses the predefined `CI_JOB_TOKEN`. "Protected" variables
reach only protected refs, which is why step 1 protects `v*`.

## Cutting a release

Publish a release on GitHub (Releases → Draft a new release, new tag
`v0.1.0` on `main`, Publish), or from the command line:

```sh
gh release create v0.1.0 --target main --title "Hubra 0.1.0" --generate-notes
```

Publishing starts images.yml; the new tag starts the mirror. A tag pushed
without a GitHub release builds no images, and the GitLab release then fails
after `GHCR_WAIT_MINUTES`.

The release notes group the commit subjects since the previous `v*` tag by
Conventional Commit type (`scripts/changelog.sh v0.1.0` shows them locally).

## Cluster pull secret

Unchanged: the cluster pulls from GHCR with the `ghcr-pull` secret, which
`deploy/create-secrets.sh` creates from `GHCR_USER` and `GHCR_TOKEN`
(a GitHub token with `read:packages`), and the namespace's default
ServiceAccount uses it (`deploy/app/serviceaccount.yaml`). If the cluster's
secrets live in the GitLab GitOps repo (SOPS or Sealed Secrets), create the
same `kubernetes.io/dockerconfigjson` Secret there instead.
