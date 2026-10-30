# CI and branch protection

Two levels of checks: fast ones on every pull request into `main`, and the
full set only when a release is being prepared.

| Workflow | Runs on | What it runs |
| --- | --- | --- |
| `ci.yml` (CI) | pull requests into `main`, pushes to `main` | `lint` (ruff, eslint and `tsc` in the three frontends, Compose files, Kustomize + kubeconform, shellcheck), backend unit tests, frontend unit tests |
| `release-checks.yml` (Release checks) | `release/*` branches (create and push), pull requests into `release/*`, before every image build, by hand | all of `ci.yml` without the path filter, plus dependency audits (pip-audit, npm audit), the image builds and the Compose stack with the browser tests |
| `images.yml` (Images) | GitHub release published, by hand | `release-checks.yml` first, then builds and pushes the images |

On pull requests the test jobs run only when the change touches their code:
the backend tests for `app/backend/`, `plugins/` and `settings.yaml`, the
frontend tests for `app/*frontend/`, `packages/` and `plugins/`, and both
for a change to `ci.yml` itself. Anything else (other workflows, `deploy/`,
`modules/`, `scripts/`, docs) runs `lint` only. Draft pull requests run
nothing until they are marked ready for review.

## Required checks

A required check that never reports blocks the merge forever, so the
required checks are jobs that always run:

- `lint` runs on every pull request into `main`.
- `tests` is an aggregate job. It waits for the test jobs and passes when
  each passed or was skipped. Add a new test job to its `needs` list, not to
  branch protection.
- `release-checks` is the aggregate of `release-checks.yml`; it passes only
  when every job passed.

The workflows have no workflow-level `paths` filter on purpose: a filtered
workflow does not run at all, and its required checks would stay pending.

## Release flow

1. Optional: Actions > Release checks > Run workflow on `main`, to see the
   full checks before cutting the branch.
2. Create `release/1.2` from `main`. The full checks run on it.
3. Fixes for the release go in as pull requests into `release/1.2`, each
   with the full checks. Merge them back into `main` too.
4. Publish a GitHub release `v1.2.0` with target `release/1.2`. Images runs
   the full checks again on that commit and builds the images only if they
   pass.

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
