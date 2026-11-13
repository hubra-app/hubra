# CI and branch protection

Two levels of checks: fast ones on every pull request into `main`, and the
full set only when a release is being prepared.

| Workflow | Runs on | What it runs |
| --- | --- | --- |
| `ci.yml` (CI) | pull requests into `main`, pushes to `main` | `lint` (ruff, pyright, eslint and `tsc` in the frontends, Compose files, shellcheck), backend unit tests on SQLite and on Postgres 18 (`backend-postgres`, also the tests SQLite skips), both in parallel with `pytest -n auto`, frontend unit tests, and when a change reaches what the browser sees the Compose stack with the browser tests; `release-check` (`scripts/release_check.py` and its tests, for the declared version) when the version, the changelogs or the release scripts change |
| `release-checks.yml` (Release checks) | `release/*` branches (create and push), pull requests into `release/*`, before every image build, by hand | all of `ci.yml` without the path filter (except its Postgres run, which release checks run with the pg_dump 18 client), plus the backend tests on Postgres 18 (`backend-postgres`, which also runs the tests SQLite skips), dependency audits (pip-audit, npm audit), the image builds and the Compose stack with the browser tests |
| `release-dry-run.yml` (Release dry run) | by hand | the `check` job of Release for the version in `pyproject.toml`, without a tag, plus whether the tag or release exists; release notes in the summary |
| `release.yml` (Release) | `v*` tag pushed | checks the tag, runs Images, waits for approval (environment `release`), then tags and signs the images, publishes the GitHub release, calls Release branch and the GitLab mirror ([releases.md](releases.md)) |
| `images.yml` (Images) | called by Release (a `v*` tag); no manual runs | `release-checks.yml` first, then builds and pushes the images |
| `release-branch.yml` (Release branch) | called by Release (not pre-releases) | creates `release/X.Y` at the release's commit if it does not exist yet |

On pull requests and pushes to `main`, lint and the test jobs run only for
the parts of the code the change touches (the `changes` job decides):

| Part | Paths |
| --- | --- |
| ruff, pyright | `app/backend/`, `plugins/` |
| eslint + `tsc`, per frontend | that frontend's `app/*frontend/` folder, `packages/`, `plugins/` |
| Compose, shellcheck | `docker-compose*.yml`, `.env.example`, `settings.yaml`, `modules/`, `scripts/`, `app/deploy/` |
| backend tests | `app/backend/`, `plugins/`, `settings.yaml` |
| frontend tests | `app/*frontend/`, `packages/`, `plugins/` |
| browser tests (`browser-tests`, see below) | `app/*frontend/`, `packages/`, `plugins/`; the backend code that serves the API (`app/backend/` without `tests/`, `hubra/core/tasks/` and `hubra/templates/`), `migrations/`, `CHANGELOG.md`, `CHANGELOG.de.md` and `ROADMAP.yaml` (What's new shows them); `docker-compose.yml`, `app/deploy/`, `settings.yaml`; the e2e setup (`.github/e2e/`, `scripts/init-env.sh`, `smoke-test.sh`, `e2e-accounts.sh`) |

A change to `ci.yml` itself runs everything, and so does a push whose base
is unknown (new branch, force push). The browser tests run on pull requests
so a screen change that breaks them fails its own pull request instead of
the next image build, and on pushes to `main` so two merges that only break
them together show up right away. A backend change the browser cannot see
(unit tests, Celery tasks, mail templates) and a docs change skip them.
Anything else (docs, the other workflows, `brand/`,
`tools/`) runs nothing: `lint` and `tests` report as skipped. Text files
run nothing wherever they are: Markdown files (so also `CHANGELOG.md` and
`CHANGELOG.de.md`), `README` files and `.gitignore` files. The changelog
checks in the backend tests still run in release-checks before a release.
A version bump (`bnb bump`) runs nothing as well: a change to
`app/backend/pyproject.toml` that only edits the `version` line is left out,
and a changelog change that only adds `## [x.y.z] - date` headings does not
count for the browser tests. Any other line in those files runs the checks
as before. Draft pull
requests run nothing until they are marked ready for review.

## Browser tests

`browser-tests` builds the four app images, starts the Compose stack and runs
the Playwright tests in `app/frontend/e2e` against it. What keeps it short:

- The images build with Buildx and a layer cache in the GitHub Actions cache
  (scope `e2e-<image>`). Pushes to `main` fill it; a pull request reads it
  plus its own cache from earlier pushes, so an image the change did not
  touch is not rebuilt.
- `npm ci` and the Playwright browser install run while the stack starts,
  and only the headless shell is downloaded.
- The tests run in three parallel workers (`E2E_WORKERS=3`). Each worker has
  its own club and platform-admin account (`scripts/e2e-accounts.sh`, names
  in `app/frontend/e2e/env.ts`), so the tests of one worker never see another
  worker's changes. A spec file runs in one worker, top to bottom.
  `.github/e2e/docker-compose.e2e.yml` gives the backend two CPUs and four
  gunicorn workers for that; the production limits in `docker-compose.yml`
  stay as they are.

Release checks (`compose-smoke`) run the same tests the same way, but build
the images without a cache.

Timings (November 2026, 71 tests): the job took 5m40 before (build 1m28,
stack 1m07, installs 36s, tests 2m18 in one worker). Now it takes about 2m50
with a warm cache (build 20s, stack and installs together 41s, accounts 10s,
tests 1m15); with a cold cache the build takes about 1m45 instead of 20s.

A test that changes something all workers share (a platform setting, the
plugin catalogue) must not depend on it staying that way and has to put it
back at the end, as `step-up-passkey.spec.ts` does with the plugin update
mode. Club and account changes are safe: each worker has its own.

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
2. Push tag `v1.2.0` on `main` ([releases.md](releases.md)). Release runs
   the full checks on that commit, builds the images only if they pass, and
   waits for your approval before anything is called 1.2.0.
3. After the release is published, `release-branch.yml` creates `release/1.2`
   at that commit (one branch per minor version; pre-releases create none,
   and an existing branch is never moved).

**Patches:** fixes go in as pull requests into `release/1.2`, each with the
full checks, and are merged back into `main` too. Push tag `v1.2.1` on
`release/1.2`.

**Stabilizing before `v1.2.0`** (to keep merging features into `main`
meanwhile): create `release/1.2` from `main` by hand, fix it there, then
push tag `v1.2.0` on `release/1.2`. The workflow leaves the
existing branch as it is.

Images builds only the images whose files changed since their last build
and gives the others the new tags on the same digest; set the repository
variable `HUBRA_BUILD_ALL=true` to rebuild all in the next release. Versions and tags:
[release-guidelines.md](release-guidelines.md).

Images are built only for releases; there are no manual image builds,
because the cluster's Flux follows version releases.

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
