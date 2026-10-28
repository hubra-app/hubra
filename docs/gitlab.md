# Releases on GitLab

GitHub (`hubra-app/hubra`) stays the place for code, pull requests and their
checks. A GitLab project gets a copy of `main` and the tags and turns version
tags into releases:

```
GitHub main ──mirror-gitlab.yml──▶ GitLab main ──▶ checks
GitHub tag v1.2.3 ───────────────▶ GitLab tag  ──▶ checks ─▶ images ─▶ GitLab Release
```

| Pipeline on GitLab | Jobs |
| --- | --- |
| `main`, merge requests | `backend` (ruff, pytest), `frontends` (lint, build, plugin frontends), `compose`, `kubernetes` (kustomize + kubeconform of every overlay), `shellcheck`, the same as `.github/workflows/ci.yml` |
| tag `v1.2.3` or `v1.2.3-rc.1` | the checks, then `images` builds the seven images and pushes them to the project's Container Registry, then `release` creates a GitLab Release with the changelog and the image digests |

Only tags in semver form (`v` + `MAJOR.MINOR.PATCH`, optional `-pre.release`)
start a release. Any other tag runs nothing.

## Images

`$CI_REGISTRY_IMAGE/<image>`, for example
`registry.gitlab.com/<group>/hubra/backend`, for `backend`, `frontend`,
`admin-frontend`, `sso-frontend`, `haraka`, `zonemta` and `cert-watcher`.

| Tag | Example |
| --- | --- |
| `1.2.3` | every release |
| `1.2`, `1` | final releases only, moved by the newest patch release |
| `buildcache` | BuildKit layer cache, not for running |

There is no `latest`. The cluster pins a release, ideally by digest: each
GitLab Release ends with an `images:` block for the overlay
(`deploy/clusters/contabo/kustomization.yaml`), with `newName` and `digest`
for every image. Paste it over the overlay's `images:` and commit; Flux rolls
out exactly those images and nothing else.

## Setup

1. **GitLab project.** Create an empty project, for example
   `<group>/hubra` (private). Settings → General → Visibility: keep the
   Container Registry on. Settings → Repository → Protected tags: protect
   `v*` (allowed to create: Maintainers).
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
4. **Runners.** The checks run on any Docker runner. `images` uses
   Docker-in-Docker, so it needs a runner with `privileged = true`; the
   GitLab.com instance runners have that. A runner on the k3s cluster needs
   privileged pods for this job.

## CI variables

GitLab needs none for releases: the registry login (`CI_REGISTRY`,
`CI_REGISTRY_USER`, `CI_REGISTRY_PASSWORD`) and the release token
(`CI_JOB_TOKEN`) are predefined.

| Where | Name | What |
| --- | --- | --- |
| GitHub, Actions variable | `GITLAB_MIRROR_URL` | GitLab repository path, `gitlab.com/<group>/hubra.git` |
| GitHub, Actions secret | `GITLAB_MIRROR_TOKEN` | GitLab project access token, Maintainer, `write_repository` |
| GitLab, CI/CD variable (optional) | `HUBRA_SKIP_MAIN_CHECKS` | `true` skips the pipeline on `main`, which GitHub already checked. Tags always run the checks. |

## Cutting a release

```sh
git tag -a v0.1.0 -m "Hubra 0.1.0"
git push origin v0.1.0        # to GitHub; the mirror forwards it
```

The release notes group the commit subjects since the previous `v*` tag by
Conventional Commit type (`scripts/changelog.sh v0.1.0` shows them locally).

## Cluster pull secret

The registry of a private project needs credentials. In GitLab, Settings →
Repository → Deploy tokens → new token with scope **read_registry**. Then,
with cluster access:

```sh
kubectl -n hubra create secret docker-registry gitlab-registry \
  --docker-server=registry.gitlab.com \
  --docker-username=<deploy token username> \
  --docker-password=<deploy token>
```

and add it to the namespace's default ServiceAccount
(`deploy/app/serviceaccount.yaml`, next to `ghcr-pull`):

```yaml
imagePullSecrets:
  - name: ghcr-pull
  - name: gitlab-registry
```

If the cluster's secrets live in the GitLab GitOps repo (SOPS or Sealed
Secrets), create the same Secret there instead of with kubectl.
