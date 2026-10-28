# Subdomain Migration Guide

The Flask API is served from `api.vollbuild.ch`; the frontend SPA is served
from `cos.vollbuild.ch` (and the apex `vollbuild.ch`). Both share the
registrable domain `vollbuild.ch`, so JWT cookies use `Domain=.vollbuild.ch`
and are sent cross-subdomain by the browser.

**Auth scheme in use:** JWT-in-cookies via Flask-JWT-Extended. No Flask-Login
server sessions. (`Session`/`DeviceSession` tables exist only for revocation
tracking, not for auth.)

---

## Operator note (Traefik) — read first

> **Do not add CORS headers for `api.vollbuild.ch` in Traefik.** The Flask app
> owns CORS (single source of truth). A duplicate `Access-Control-Allow-Origin`
> header makes browsers reject every response.
>
> Ensure `crowdsec@file` and `error-pages-middleware` pass `OPTIONS` preflight
> through unchanged (200/204 with CORS headers, **not** rewritten to HTML error
> pages). Preflight carries no credentials and must not be blocked.
>
> The backend's Traefik labels reference `tls.certresolver=letencrypt`, which is
> **defined in the external Traefik** — no ACME/certresolver/TLS-store config
> lives in this repo. TLS terminates upstream; the app only sees HTTP.

---

## 1. Cookie SameSite + Domain + path

**Applied in `app/backend/hubra/config.py`:**

```python
JWT_TOKEN_LOCATION: list = ["cookies"]
JWT_COOKIE_SAMESITE: str = os.environ.get("JWT_COOKIE_SAMESITE", "Lax")
JWT_COOKIE_DOMAIN: str | None = os.environ.get("JWT_COOKIE_DOMAIN") or None
JWT_COOKIE_SECURE: bool = (
    os.environ.get("JWT_COOKIE_SECURE", "").lower() in ("true", "1", "yes")
    or os.environ.get("FLASK_ENV") == "production"
)
JWT_COOKIE_CSRF_PROTECT: bool = True
JWT_SESSION_COOKIE: bool = False  # persistent cookies (max_age honoured)
```

**`.env` / deployment:**

```
JWT_COOKIE_SAMESITE=Lax
JWT_COOKIE_DOMAIN=.vollbuild.ch
JWT_COOKIE_SECURE=true
```

> **SameSite=Lax rationale:** `api.vollbuild.ch` and the frontend are subdomains
> of the same registrable domain (`vollbuild.ch`), so requests between them are
> **same-site**. `Lax` cookies ARE sent on these cross-subdomain requests and is
> the more secure choice (it blocks cross-site POST, the main CSRF vector).
> `SameSite=None; Secure` would be required only if a frontend origin ever lived
> on a *different* registrable domain — that weakens CSRF posture and is **not**
> used here. If it ever is, document it and make CSRF tokens mandatory.

### Cookie path — kept at `/` (do NOT narrow)

All JWT + CSRF cookies use `Path=/`. Narrowing the refresh-cookie path (e.g.
`/api/v1/auth/refresh`) sounds good in theory but **breaks cross-subdomain
CSRF double-submit**: the frontend SPA at `cos.vollbuild.ch/` reads
`csrf_access_token` / `csrf_refresh_token` via `document.cookie` to send the
`X-CSRF-TOKEN` header, and a cookie with `Path=/api/...` is **not visible** in
`document.cookie` on the SPA's `/` path. Keep `Path=/`.

### Final cookie attributes (production)

| Cookie                  | Secure | HttpOnly | Domain         | SameSite | Path |
| ----------------------- | ------ | -------- | -------------- | -------- | ---- |
| `access_token_cookie`   | Yes    | Yes      | `.vollbuild.ch`| Lax      | `/`  |
| `refresh_token_cookie`  | Yes    | Yes      | `.vollbuild.ch`| Lax      | `/`  |
| `csrf_access_token`     | Yes    | No (JS)  | `.vollbuild.ch`| Lax      | `/`  |
| `csrf_refresh_token`    | Yes    | No (JS)  | `.vollbuild.ch`| Lax      | `/`  |
| `remembered_email`      | Yes    | No (JS)  | `.vollbuild.ch`| Lax      | `/`  |

> `HttpOnly=False` on the CSRF cookies and `remembered_email` is intentional —
> the frontend reads them via `document.cookie`. The JWT value cookies stay
> `HttpOnly` so XSS cannot exfiltrate tokens.

### CSRF (double-submit)

`JWT_COOKIE_CSRF_PROTECT=True` — a readable CSRF cookie plus a required
`X-CSRF-TOKEN` header on `POST`/`PUT`/`PATCH`/`DELETE`. The `X-CSRF-TOKEN`
header is in the CORS `Allow-Headers` list, and the frontend sends it on every
state-changing request (`app/frontend/src/api/client.ts`).

---

## 2. CORS (single source of truth — Flask)

`CORS_ORIGINS` (plural) is a comma-separated allowlist read by `config.py`.
The singular `CORS_ORIGIN` is still accepted as a fallback. **No wildcards.**

**`app/backend/hubra/__init__.py`:**

```python
cors.init_app(
    app,
    resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
    supports_credentials=True,          # cookies flow cross-origin
    allow_headers=["Content-Type", "X-CSRF-Token"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    expose_headers=["Content-Disposition", "X-Total-Count"],
    max_age=600,
)
```

> `Authorization` is **not** in `allow_headers` — auth is cookie-only.
> `X-Access-Token` was removed (it was only ever sent by the backend to
> WildDuck, never by the browser to the API).

### Vary: Origin safeguard

A dedicated `after_request` (registered **before** `cors.init_app` so it runs
**after** flask-cors's own after_request, since Flask runs after_request in
reverse registration order) appends `Origin` to `Vary` whenever an
`Access-Control-Allow-Origin` header is present and `!= *`. This guarantees
shared caches don't serve one origin's CORS headers to another, even if a
future flask-cors version changes its default.

**`.env` / deployment:**

```
CORS_ORIGINS=https://vollbuild.ch,https://cos.vollbuild.ch,http://localhost:5173
```

---

## 3. Preflight (OPTIONS) must not be blocked

- **Auth/RBAC:** Flask's automatic OPTIONS handler bypasses `@jwt_required` and
  `@permission_required`, so preflight never hits auth.
- **Rate limiting:** `@limiter.request_filter` in `extensions.py` exempts
  `request.method == "OPTIONS"` so flask-limiter returns 200, not 429.
- **CrowdSec:** runs as a Traefik middleware (`crowdsec@file`) — see the
  operator note above; it must pass OPTIONS through unchanged.

---

## 4. ProxyFix / behind-proxy correctness

**`app/backend/wsgi.py`:**

```python
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
```

One proxy hop: external Traefik (edge) → Flask. **Caddy is NOT in the API
path** (it only fronts the frontend SPA on `cos.vollbuild.ch`);
`api.vollbuild.ch` routes directly Traefik → `backend:5000`.

- `x_for=1` trusts exactly one `X-Forwarded-For` entry so `request.remote_addr`
  is the real client IP — critical for CrowdSec (Traefik middleware) and
  flask-limiter keying. Over-trusting (`x_for=2`) would let a spoofed header
  shift IP attribution.
- `x_proto=1` so the app knows requests are HTTPS (correct `Secure` cookie
  behaviour, correct scheme in generated URLs).
- `x_host=1` so `request.host` is the real host (`api.vollbuild.ch`).

> The old `x_for=2` and the Caddyfile `(proxy_headers)`/`(backend_proxy)`
> snippets were leftovers from when Caddy proxied `/api/*` (Traefik → Caddy →
> Flask). They are annotated as legacy in `app/deploy/Caddyfile`.

---

## 5. Email links — FRONTEND_BASE_URL (not the API host)

The API now has its own host, so `request.url_root` resolves to
`https://api.vollbuild.ch/` — wrong for links that must open the frontend SPA.

- Added `FRONTEND_BASE_URL` (env, e.g. `https://cos.vollbuild.ch`) to
  `config.py`.
- `services/email.py:_get_base_url()` returns `FRONTEND_BASE_URL`, **not**
  `request.url_root`. (The request-context fallback was removed — every email
  link must point at the frontend, never the API host.)
- `auth/routes.py` password-reset and email-verification links use
  `_get_base_url()`.

**`.env` / deployment:**

```
FRONTEND_BASE_URL=https://cos.vollbuild.ch
```

---

## 6. `remembered_email` cookie (cross-subdomain fix)

Previously set **host-only** and **`HttpOnly=True`**, so the frontend on
`cos.vollbuild.ch` could neither receive nor read it —
`getRememberedEmail()` always returned `""`.

Fixed via `_set_remembered_email_cookie` / `_clear_remembered_email_cookie`
helpers in `auth/routes.py`:

- `Domain=.vollbuild.ch` (shared parent domain)
- `HttpOnly=False` (frontend reads it via `document.cookie`)
- `SameSite=Lax`, `Secure` mirrors JWT cookies
- Logout clears it with the **same** domain so it actually deletes.

---

## 7. CSP — frontend-only, not API

CSP, Permissions-Policy, and Accept-CH are set by **Caddy** on frontend HTML
responses only (`app/deploy/Caddyfile`). They were removed from the Flask
`after_request` hook because CSP applies to HTML documents, not JSON API
responses.

The frontend CSP includes `connect-src 'self' https://api.vollbuild.ch` to
allow the browser to make cross-origin API calls.

---

## 8. Caddy configuration

Caddy is a pure frontend proxy — no API or autodiscover routing:

```caddy
:80 {
  header {
    Content-Security-Policy "default-src 'self'; ...; connect-src 'self' https://api.vollbuild.ch; frame-ancestors 'none'"
    # ... other security headers
  }
  reverse_proxy * frontend:80
}
```

The `/api/*`, `/autodiscover/*`, and `/Autodiscover/*` proxy blocks were
removed. API traffic goes directly to the backend via Traefik
(`api.vollbuild.ch` → `backend:5000`). The `(proxy_headers)` / `(backend_proxy)`
snippets are retained as legacy reference but no longer referenced.

---

## 9. Frontend changes (cross-origin gotchas)

- API base URL → `https://api.vollbuild.ch/api` (`VITE_API_BASE`, compose env).
- Every request sends `credentials: 'include'` (`apiFetch` in
  `app/frontend/src/api/client.ts`). Without this the cookie isn't sent and
  every call 401s.
- On state-changing requests, the `X-CSRF-TOKEN` header is read from the
  `csrf_access_token` cookie and sent (refresh uses `csrf_refresh_token`).
- No assumption that API and frontend share an origin (no relative `/api/...`
  URLs, no same-origin cookie reads other than the cross-subdomain CSRF cookies).

---

## 10. Same-origin assumptions that had to change

1. **Email link generation** — `request.url_root` (API host) →
   `FRONTEND_BASE_URL` (frontend host). Files: `services/email.py`,
   `api/auth/routes.py`.
2. **`remembered_email` cookie** — host-only + `HttpOnly` (unreadable
   cross-subdomain) → `Domain=.vollbuild.ch` + `HttpOnly=False`.
3. **ProxyFix hop count** — `x_for=2` (stale "Traefik→Caddy→Flask") →
   `x_for=1` (Traefik→Flask only); fixes CrowdSec/rate-limit IP attribution.
4. **CORS allowlist** — added apex `https://vollbuild.ch` (was
   `cos.vollbuild.ch` + localhost only).

No change needed to: frontend `credentials:'include'`, `X-CSRF-TOKEN` send,
CSP `connect-src`, logout `unset_jwt_cookies`, cookie `SameSite=Lax` /
`Domain=.vollbuild.ch` (already correct).

---

## 11. Remaining low / info items

| Item                             | File                             | Action                                                                                                                    |
| -------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| HSTS `preload` flag              | `hubra/__init__.py`          | Add `; preload` to the HSTS value when domain is submitted to the preload list                                            |
| WildDuck API HTTPS               | `hubra/config.py`            | Assert `WILDDUCK_API_URL.startswith("https://")` in production startup check                                              |
| Frontend `apiFetch` content-type | `app/frontend/src/api/client.ts` | Check `Content-Type: application/json` before calling `.json()` to avoid confusing errors when a proxy returns HTML       |
| Old domain redirect              | `docker-compose.override.yaml`   | `cos.public.reyki.net` → `cos.vollbuild.ch` redirect is configured; remove the redirect labels once migration is complete |
