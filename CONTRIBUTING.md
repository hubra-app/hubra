# Contributing to Hubra

Thank you for wanting to help. Bug reports, ideas and translation fixes are
always welcome. Code is welcome too, but please read
[Before you write code](#before-you-write-code) first, because Hubra is not
open source.

By taking part you agree to the [code of conduct](CODE_OF_CONDUCT.md).

## Ways to help

| You want to… | Do this |
| --- | --- |
| Report a security problem | **Not in an issue.** Follow [SECURITY.md](SECURITY.md). |
| Report a bug | Open a [bug report](https://github.com/hubra-app/hubra/issues/new?template=bug_report.yml). Club members and admins can also use [support.hubra.club/melden](https://support.hubra.club/melden). |
| Suggest a feature | Check the [roadmap](https://support.hubra.club/roadmap) and vote if it is there; otherwise open a [feature request](https://github.com/hubra-app/hubra/issues/new?template=feature_request.yml) or post an idea at [support.hubra.club/idee](https://support.hubra.club/idee). |
| Ask a question | Use [support.hubra.club/kontakt](https://support.hubra.club/kontakt) or write to [hi@hubra.club](mailto:hi@hubra.club). |
| Fix a translation | Clubs can suggest changes in the club app; see [Translations](#translations). |
| Write a plugin | Start from [hubra-plugins-template](https://github.com/hubra-app/hubra-plugins-template) and read [docs/plugins.md](docs/plugins.md). |
| Fix a bug or build a feature | Read on. |

## Before you write code

Hubra's source is public so it can be read, but it is **all rights
reserved** (see [LICENSE](LICENSE)). Copying, modifying or running it needs
the copyright holder's written permission. In practice:

1. **Open an issue first** and say what you would like to change. Wait for
   a maintainer to agree before you spend time on it. Pull requests that
   were not agreed in an issue may be closed.
2. **Sign the contributor licence agreement.** We can only merge your work
   if you give us the right to use it. On your first pull request, the
   CLA Assistant bot posts a link to the [contributor licence agreement](CLA.md);
   sign it once with your GitHub account and it covers all your later pull
   requests. You keep the copyright in your work: the agreement is a licence,
   not a transfer.
3. A maintainer's go-ahead in the issue counts as the written permission to fork and
   change the code for that pull request. It does not cover running Hubra
   for anything other than developing and testing your change.

## Development setup

- Run the stack locally with Docker Compose:
  [docs/run-with-docker.md](docs/run-with-docker.md).
- Frontend development (Vite dev servers, the shared `packages/`):
  [docs/frontend.md](docs/frontend.md).
- Backend and API: [docs/architecture.md](docs/architecture.md),
  [docs/api-overview.md](docs/api-overview.md) and
  [app/backend/API.md](app/backend/API.md).
- Settings and feature flags: [docs/configuration.md](docs/configuration.md).

The repository layout is described in the [README](README.md#project-structure).

## Making a change

1. **Branch from `main`.** `main` is protected; every change goes in
   through a pull request.
2. **Keep it focused.** One pull request, one change. Unrelated clean-ups go
   in their own pull request.
3. **Commit messages** follow
   [Conventional Commits](https://www.conventionalcommits.org/) with the
   area as the scope, for example
   `fix(manage): seed platform permissions on start` or
   `feat(club-app): page tabs wrap on phones`. Write the subject so it says
   what changes for the person using Hubra.
4. **Database changes** need an Alembic migration in
   `app/backend/migrations/` (`flask db migrate`). Several heads after
   merging `main` are fine; see [docs/migrations.md](docs/migrations.md).
5. **Changelog.** Anything a user or operator would notice gets an entry
   under `## [Unreleased]` in `app/backend/CHANGELOG.md` **and** the same
   entry, in German, in the same place in `app/backend/CHANGELOG.de.md`.
   The apps show these under "What's new".
6. **Docs.** Update the page in `docs/` that describes what you changed, and
   the README table if you add a page.
7. **Screenshots.** For a change you can see, commit screenshots under
   `docs/screenshots/<topic>/` and embed them in the pull request: desktop,
   phone, and dark mode where it matters.

### Code style

- **Backend:** Python 3.13, Flask, SQLAlchemy. `ruff` must pass.
- **Frontends:** TypeScript, React, Mantine. `eslint` and `tsc` must pass.
  Use the shared components and colour tokens from `packages/ui` and follow
  [docs/design-spec.md](docs/design-spec.md): no hard-coded colours, an
  `aria-label` on every icon-only button, and text that meets WCAG AA
  contrast in light and dark mode.
- `.editorconfig` and `.pre-commit-config.yaml` hold the formatting rules;
  `pre-commit install` runs them on every commit.

### Translations

Hubra's interface is German first (`de-CH`), with English. Every new text
needs both. The frontend strings live in `app/frontend/src/locales/`;
`i18n.test.ts` checks that the languages have the same keys. Translations
are managed on the platform, so clubs suggest changes instead of editing
them; a fix to a shipped string goes in a pull request like any other change.

## Tests

Run what your change touches before you push:

```bash
# Backend
cd app/backend
python -m pytest -n auto

# A frontend (app/frontend, app/admin-frontend, app/sso-frontend, app/support-frontend)
npm run lint
npm run build
npm test

# Browser tests (needs the running stack)
cd app/frontend
npx playwright test
```

Add or update tests for what you change. A bug fix should come with a test
that fails without it.

## Pull requests

- Fill in the [pull request template](.github/pull_request_template.md).
- Open it as a **draft** while you are still working. CI does not run on
  drafts; mark it ready for review when you want the checks.
- The required checks are `lint` and `tests`. Which jobs run depends on the
  paths you changed; [docs/ci.md](docs/ci.md) explains it.
- Keep your branch up to date by merging `main` into it.
- A maintainer reviews and merges. Please be patient: Hubra is maintained by
  a small team.
