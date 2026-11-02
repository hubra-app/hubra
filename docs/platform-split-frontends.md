# Should the frontends get their own images or repos?

Status: recommendation, nothing built. Written 2026-11-02 with the platform
backend split ([platform-backend.md](platform-backend.md)).

## Short answer

**Images: they already are separate.** The club app (`frontend`), manage
(`admin-frontend`) and SSO/join (`sso-frontend`) are three images and three
Deployments. A manage change already only needs the `admin-frontend` tag
bumped; the club app and the backends don't restart. Nothing to build.

**Repos: no, keep them in this repo.** Splitting costs more than it gives at
Hubra's size. Revisit when a separate team owns one frontend, or the club app
ships on its own schedule (for example a native app wrapper).

## What we have today

| | Club app | Manage | SSO / join |
| --- | --- | --- | --- |
| Source | `app/frontend` | `app/admin-frontend` | `app/sso-frontend` |
| Image | `frontend` | `admin-frontend` | `sso-frontend` |
| Talks to | club backend | platform backend (+ club backend for sign-in) | club backend |
| Shared code | `packages/api-client`, `packages/ui`, `brand/` | same | same |

Each image is nginx with the built files; host names come in at container
start, so one image fits every install. A frontend rollout swaps an nginx pod,
takes seconds and has no gap (readiness probe, one pod surges first).

## Separate repos: tradeoffs

**For**

- Each repo's history and CI only covers its own app.
- Access could be granted per app (an outside designer on manage only).
- Release cadence per app is explicit.

**Against**

- **API changes stop being one PR.** Most features touch an API route and the
  screen that uses it in the same change (this week: maintenance windows,
  usage trends, Discord status). Across repos that is two PRs, merged in the
  right order, with a version contract in between.
- **Shared packages need publishing.** `packages/api-client` and
  `packages/ui` would become versioned npm packages (GitHub Packages), with a
  release and a bump in three repos for every shared change. Today a type
  change is checked by `tsc` in all three apps in the same CI run.
- **The browser tests span apps.** The e2e suite runs the Compose stack with
  all three frontends and the backend. Split repos need a cross-repo test
  setup, or lose those tests.
- **Actions minutes.** Every repo runs its own install, lint and build. The
  plugin repos already show the overhead (checkout of hubra main, token
  secrets, release workflow per repo).
- **No deploy benefit.** Independent rollout is already possible because the
  images are separate; a repo split adds nothing there.

## What I'd do instead (cheap, optional)

1. **Pin each frontend tag on its own** in the Contabo overlay when a fix
   concerns one app, the same way as `platform-backend`. Already possible.
2. **Build only what changed** on manual Images runs: a paths filter per
   matrix entry, so a manage-only fix doesn't rebuild the club app. Saves
   minutes; releases still build everything so tags stay aligned.
3. **CODEOWNERS** per `app/*` folder if another person starts working on one
   app, instead of a repo split.

## If you still want split repos

Order of work, about two to three days:

1. Publish `@hubra/api-client` and `@hubra/ui` to GitHub Packages from this
   repo; switch the three apps to the published versions.
2. Move each app with history (`git subtree split`, as for the plugins) to
   `hubra-app/hubra-frontend`, `hubra-admin`, `hubra-sso`, each with lint,
   unit tests, Images and a release workflow.
3. Move the browser tests to a small integration repo (or keep them here)
   that pulls the released images.
4. Pin the API version each frontend release needs (`/api/v1/version`), and
   show a warning in the app when the backend is older.
