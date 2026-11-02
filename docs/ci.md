# CI and branch protection

Two levels of checks: fast ones on every pull request into `main`, and the
full set only when a release is being prepared.

| Workflow | Runs on | What it runs |
| --- | --- | --- |
| `ci.yml` (CI) | pull requests into `main`, pushes to `main` | `lint` (ruff, eslint and `tsc` in the three frontends, Compose files, Kustomize + kubeconform, shellcheck), backend unit tests, frontend unit tests, and on pull requests that change a frontend the Compose stack with the browser tests |
| `release-checks.yml` (Release checks) | `release/*` branches (create and push), pull requests into `release/*`, before every image build, by hand | all of `ci.yml` without the path filter, plus dependency audits (pip-audit, npm audit), the image builds and the Compose stack with the browser tests |
| `images.yml` (Images) | GitHub release published, by hand | `release-checks.yml` first, then builds and pushes the images |
| `release-branch.yml` (Release branch) | GitHub release published (not pre-releases) | creates `release/X.Y` at the release's commit if it does not exist yet |

On pull requests and pushes to `main`, lint and the test jobs run only for
the parts of the code the change touches (the `changes` job decides):

| Part | Paths |
| --- | --- |
| ruff | `app/backend/`, `plugins/` |
| eslint + `tsc`, per frontend | that frontend's `app/*frontend/` folder, `packages/`, `plugins/` |
| Compose, Kustomize + kubeconform, shellcheck | `docker-compose*.yml`, `.env.example`, `settings.yaml`, `deploy/`, `modules/`, `scripts/`, `app/deploy/` |
| backend tests | `app/backend/`, `plugins/`, `settings.yaml` |
| frontend tests, browser tests (`browser-tests`, about five minutes, pull requests only) | `app/*frontend/`, `packages/`, `plugins/` |

A change to `ci.yml` itself runs everything, and so does a push whose base
is unknown (new branch, force push). The browser tests run on pull requests
so a screen change that breaks them fails its own pull request instead of
the next image build. Anything else (docs, the other workflows, `brand/`,
`tools/`) runs nothing: `lint` and `tests` report as skipped. Draft pull
requests run nothing until they are marked ready for review.

## Required checks

A required check that never reports blocks the merge forever, so the
required checks are jobs that always report. A job skipped by its `if`
reports as skipped, which GitHub counts as passed:

- `lint` runs when the change touches code it checks and is skipped
  otherwise. If the `changes` job fails, `lint` runs every step rather than
  being skipped.
- `tests` is an aggregate job. It waits for the test jobs and passes when
  each passed or was skipped. Add a new test job to its `needs` list, not to
  branch protection.
- `release-checks` is the aggregate of `release-checks.yml`; it passes only
  when every job passed.

The workflows have no workflow-level `paths` filter on purpose: a filtered
workflow does not run at all, and its required checks would stay pending.

## Release flow

**Usual case, from `main`:**

1. Optional: Actions > Release checks > Run workflow on `main`, to see the
   full checks before publishing.
2. Publish a GitHub release `v1.2.0` with target `main`. Images runs the
   full checks on that commit and builds the images only if they pass.
3. `release-branch.yml` creates `release/1.2` at that commit by itself (one
   branch per minor version; pre-releases create none, and an existing
   branch is never moved).

**Patches:** fixes go in as pull requests into `release/1.2`, each with the
full checks, and are merged back into `main` too. Publish `v1.2.1` with
target `release/1.2`.

**Stabilizing before `v1.2.0`** (to keep merging features into `main`
meanwhile): create `release/1.2` from `main` by hand, fix it there, then
publish `v1.2.0` with target `release/1.2`. The workflow leaves the
existing branch as it is.

Images builds only the images whose files changed since their last build
and gives the others the new tags on the same digest; run it by hand with
"Build every image" to rebuild all. Versions and tags:
[release-guidelines.md](release-guidelines.md).

Manual image builds (Actions > Images > Run workflow) also run the full
checks first.

## Branch protection

Repository rulesets, in `.github/rulesets/`. Each file can be imported in
Settings > Rules > Rulesets > New ruleset > Import a ruleset.

**`main.json` (branch `main`)**

- Require a pull request before merging, 0 approvals (one maintainer, and a
  pull request author cannot approve their own pull request).
- Required status checks `lint` and `tests`, from GitHub Actions only.
  "Require branches to be up to date" is off: it makes every open pull
  request rerun after each merge. The push to `main` runs the checks again
  on the merged result.
- Block force pushes and deletion.
- No bypass list, so a red pull request cannot be merged from the API
  either. To get around the rules in an emergency, set the ruleset to
  Disabled and back.

**`release.json` (branches `release/**`)**

- Same as `main`, with `release-checks` as the required check.
- Required checks are not enforced on branch creation, so a release branch
  can be pushed straight from `main`.

**`tags.json` (tags `v*`)**

- Release tags cannot be deleted or moved once created.

## How larger projects do it

- **Fast checks gate the merge, slow checks gate the release.** Lint, type
  checks and unit tests are required on every pull request; end-to-end,
  multi-platform and long integration suites run nightly, on release
  branches, or before publishing.
- **One aggregate required check.** Projects with many or path-filtered jobs
  require a single job (often called `all-green`, `ci-ok` or `required`)
  that depends on the others with `if: always()`, so branch protection does
  not need updating when jobs change and skipped jobs do not block merges.
- **Merge queue** (GitHub merge queue, or bors in older projects). Pull
  requests are tested together with what is ahead of them before they land,
  which catches two green pull requests that break `main` when combined.
  The workflows then also listen on `merge_group`. Worth adding here if
  combined merges keep breaking `main`.
- **Release branches** with backports through pull requests, and protected,
  immutable release tags, so a published version always maps to one tested
  commit.
