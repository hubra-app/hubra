# Security Audit Report — Club Management Suite

**Date:** 2026-07-09
**Scope:** Flask/Python backend, Celery tasks, React frontend, in-repo
deployment/config surface (Docker Compose, Caddyfile, mail stack, CI).
**Method:** Defensive static code audit. Each finding traced to real
reachable code. No live/destructive testing, no weaponized exploits.

**Infra boundary:** Traefik static/dynamic config and CrowdSec bouncer /
acquisition config live **outside** this repo (only `crowdsec@file` labels in
`docker-compose.override.yaml` reference them). These are flagged as
_needs manual verification_ with an on-host checklist — not audited blind.

**Dependency audits:** `pip-audit` against `requirements.lock` — **0
vulnerabilities**. `npm audit` against `package-lock.json` — **0
vulnerabilities**. Both run 2026-07-09.

---

## Findings

Findings are severity-ordered (most severe first). Each includes the exact
code path, realistic impact, and a remediation snippet using the existing
stack.

---

### [HIGH] RBAC wildcard fallback — cross-resource authorization bypass within a blueprint (CWE-285, OWASP A01)

**Location:** `app/backend/vollbuild/api/permissions.py:229-239`
**Confirmed:** Yes

**Vulnerability:**
When the exact permission key `{blueprint}.{resource}.{action}` is not in
the user's permission set, the `permission_required` decorator falls back to
a wildcard match: it grants access if the user has **any** permission in the
same blueprint prefix that ends with the same action.

```python
# permissions.py:229-239
perm_key = _derive_perm_key(request.blueprint, resource, action)
allowed = _get_member_permission_keys(member)
if perm_key not in allowed:
    prefix = (request.blueprint or "app").removesuffix("_bp")
    if not any(
        p.startswith(f"{prefix}.") and p.endswith(f".{action}")
        for p in allowed
    ):
        return jsonify(...), 403
# ↑ if ANY perm matches {prefix}.*.{action}, access is GRANTED
```

Concrete exploit scenarios (verified against the seed permission mappings in
`__init__.py:438-580`):

- **Finance:** A user with "Manage invoices" holds
  `finance.invoices.create` but NOT `finance.transactions.create`. The
  fallback matches `finance.invoices.create` (starts with `finance.`, ends
  with `.create`) → the user can **create transactions** they were never
  granted. Same for `.update`, `.delete`, `.read` across all finance
  resources (transaction_categories, external_parties, transactions,
  invoices, overview).

- **Mail:** A user with "View mailboxes" holds `mail.aliases.read`. The
  fallback grants `mail.mailboxes.read`, `mail.member_mail.read`,
  `mail.system.read`, `mail.wildduck.read` — the user can **read system mail
  addresses and WildDuck live state** they were never granted.

- **Settings:** A user with `settings.general.write` passes the decorator
  for `settings.settings.write` via the fallback. The PUT/DELETE handlers
  have an in-handler `can_write`/`can_delete` namespace check that mitigates
  this, but `POST /settings/<key>/revert` (`routes.py:131-149`) has **no
  in-handler namespace check** — so the user can **revert any setting to its
  default**, including mail domain, SMTP config, or backup S3 settings.

**Impact:**
A user with any action-level permission in a multi-resource blueprint gets
that action on ALL resources in that blueprint. This defeats the
resource-level granularity of the RBAC system. In finance, this means a
user who can only manage invoices can also create/delete transactions
(financial integrity). In mail, a user who can view aliases can read system
mail configuration and WildDuck internal state (information disclosure).

**Remediation:**
Remove the wildcard fallback entirely. The exact-key check is sufficient —
if the user doesn't have the exact permission, deny access. The fallback was
likely added as a convenience during migration, but it undermines the entire
RBAC model.

```python
# permissions.py — replace lines 229-239 with:
            perm_key = _derive_perm_key(request.blueprint, resource, action)
            allowed = _get_member_permission_keys(member)
            if perm_key not in allowed:
                return jsonify(
                    {"error": "FORBIDDEN", "message": "Insufficient permissions"}
                ), 403
```

If a transitional period is needed (roles still using old free-text
permissions), add an explicit migration flag instead of a silent wildcard.
After removing the fallback, audit all custom roles to ensure they have the
exact permissions they need.

Additionally, add an in-handler `can_write` namespace check to the
`revert_setting` route (matching the pattern in `upsert_setting` and
`delete_setting`):

```python
# settings/routes.py — revert_setting, add before SettingService.revert_to_default:
    if not member_is_admin(current_user):
        perms = _get_member_permission_keys(current_user)
        setting = SettingService.get_setting(key)
        if setting and not SettingService.can_write(setting.namespace, key, perms):
            return api_error("FORBIDDEN", "Insufficient permissions to revert this setting", 403)
```

---

### [HIGH] Roles `is_admin` mass-assignment — privilege escalation via field-level RBAC bypass (CWE-269, OWASP A01)

**Location:** `app/backend/vollbuild/api/roles/routes.py:56-79`
**Confirmed:** Yes

**Vulnerability:**
The `update_role` endpoint is decorated with `@can_update("roles", "Update
roles")`, which sets up field-level RBAC via `g.updatable_fields`. However,
the handler **never calls `filter_updatable_fields`**. Instead, it reads
fields directly from the raw request body and sets them on the role ORM
object:

```python
# roles/routes.py:56-79
@roles_bp.patch("/<int:role_id>")
@can_update("roles", "Update roles")
def update_role(role_id: int):
    role = RoleService.get(role_id)
    body = request.get_json(silent=True) or {}
    name = body.get("name")
    # ... name validation ...
    RoleService.update(role, name, int(get_jwt_identity()))

    if "description" in body:
        role.description = body["description"]       # ← direct from body
    if "is_admin" in body:
        role.is_admin = bool(body["is_admin"])       # ← direct from body, NO auth check

    db.session.commit()
    return jsonify(_schema.dump(role)), 200
```

The `@can_update` decorator for a non-admin with field-level permissions
(e.g. only `roles.roles.update.name`) sets `g.updatable_fields = {"name"}`,
but since `filter_updatable_fields` is never called, the `is_admin` field is
still set from the body unconditionally. Even a user with the **coarse**
`roles.roles.update` permission (from "Manage roles") should NOT be able to
set `is_admin` — that should be admin-only. The `RoleCreateSchema` used for
POST (create) controls which fields are accepted, but PATCH bypasses all
schema validation.

**Impact:**
A non-admin user with "Manage roles" (which includes `roles.roles.update`)
can PATCH a role they belong to and set `is_admin: true`, granting
themselves admin bypass (`member_is_admin` returns True for any role with
`is_admin=True`). This is vertical privilege escalation to full admin.
Alternatively, a non-admin with only a field-level update permission (e.g.
`roles.roles.update.name`) can also set `is_admin` because
`filter_updatable_fields` is never called.

**Remediation:**
Use `filter_updatable_fields` and restrict `is_admin` to admin-only. Apply
schema validation to the PATCH body:

```python
# roles/routes.py — replace update_role body:
@roles_bp.patch("/<int:role_id>")
@can_update("roles", "Update roles")
def update_role(role_id: int):
    role = RoleService.get(role_id)
    body = request.get_json(silent=True) or {}

    # is_admin can only be set by admins
    if "is_admin" in body and not member_is_admin(current_user):
        return api_error("FORBIDDEN", "Only admins can change is_admin", 403)

    # Filter to updatable fields for non-admins with field-level perms
    body = filter_updatable_fields(body)

    name = body.get("name")
    if name is not None:
        if not isinstance(name, str) or not name.strip():
            return api_error("VALIDATION_ERROR", "name must be a non-empty string", 400)
        RoleService.update(role, name, int(get_jwt_identity()))

    if "description" in body:
        role.description = body["description"]
    if "is_admin" in body:
        role.is_admin = bool(body["is_admin"])

    db.session.commit()
    return jsonify(_schema.dump(role)), 200
```

Add the necessary imports (`from vollbuild.api.permissions import
filter_updatable_fields, member_is_admin, current_user`).

---

### [MEDIUM] Redis broker unauthenticated (CWE-306, OWASP A05)

**Location:** `docker-compose.yml:183-204`
**Confirmed:** Yes

**Vulnerability:**
The Redis service has no authentication configured — no `--requirepass`
command, no `REDIS_PASSWORD` env var, no `requirepass` in a config file.

```yaml
# docker-compose.yml:183-204
redis:
  image: redis:7-alpine@sha256:...
  # no command, no --requirepass, no password config
  expose:
    - "6379"
  networks:
    - internal
```

Redis is `expose`d (not `ports`), so it's only reachable from the `internal`
network. However, Redis is shared by multiple services: the backend, Celery
workers, Celery beat, WildDuck (db 3), and the rate limiter. If any one
container is compromised (e.g. via a dependency vulnerability, SSRF, or
misconfiguration), the attacker gains unauthenticated access to Redis.

Celery uses the JSON serializer (`tasks/__init__.py:68-70` — confirmed, no
pickle), so direct RCE via deserialization is not possible. However, an
attacker can:

- Read/modify Celery task arguments (which include member PII, email
  content, password hashes for mail provisioning)
- Flush the rate-limit storage (disabling all rate limits)
- Inject fake task results
- Flush the permission cache (forcing DB fallback, potential DoS)

**Impact:**
Unauthenticated access to the message broker and rate-limit storage if any
internal container is compromised. No direct RCE (JSON serializer), but
data confidentiality/integrity and rate-limit bypass.

**Remediation:**
Add Redis authentication:

```yaml
# docker-compose.yml — redis service:
redis:
  image: redis:7-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99
  command: redis-server --requirepass ${REDIS_PASSWORD}
  environment:
    - REDIS_PASSWORD=${REDIS_PASSWORD}
  # ... rest unchanged ...

# And update all Redis URLs to include the password:
# REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
# RATELIMIT_STORAGE_URI=redis://:${REDIS_PASSWORD}@redis:6379/1
```

Add `REDIS_PASSWORD=` to `.env.example` with generation instructions.

---

### [MEDIUM] MongoDB unauthenticated in mail stack (CWE-306, OWASP A05)

**Location:** `docker-compose.mail.yml:22-33`
**Confirmed:** Yes

**Vulnerability:**
MongoDB stores all WildDuck mail data (mailboxes, messages, filters) but has
no authentication or authorization enabled.

```yaml
# docker-compose.mail.yml:22-33
mongo:
  image: mongo:7 # ← mutable tag, no digest pin
  # no auth config, no MONGO_INITDB_ROOT_USERNAME/PASSWORD
  expose:
    - "27017"
```

**Impact:**
If the `internal` network is bridged or any container on it is compromised,
an attacker has full read/write access to all mail data — every member's
emails, attachments, filters, and mailbox metadata.

**Remediation:**
Enable MongoDB authentication:

```yaml
mongo:
  image: mongo:7@sha256:<pin-digest>
  environment:
    - MONGO_INITDB_ROOT_USERNAME=${MONGO_USER}
    - MONGO_INITDB_ROOT_PASSWORD=${MONGO_PASSWORD}
  # ... rest unchanged ...
```

Update the WildDuck connection string:
`APPCONF_dbs_mongo: mongodb://${MONGO_USER}:${MONGO_PASSWORD}@mongo:27017/wildduck?authSource=admin`

---

### [MEDIUM] CORS allows localhost origin in production override (CWE-942, OWASP A05)

**Location:** `docker-compose.override.yaml:43`
**Confirmed:** Yes

**Vulnerability:**
The production override sets `CORS_ORIGINS` to include `http://localhost:5173`:

```yaml
# docker-compose.override.yaml:42-43
environment:
  - CORS_ORIGINS=https://cos.vollbuild.ch,http://localhost:5173
```

This allows any script running on `localhost:5173` to make credentialed
cross-origin requests to the production API. `flask-cors` is configured with
`supports_credentials=True` (`__init__.py:121`), so cookies will be sent.

**Impact:**
If a developer runs a local dev server on port 5173 and visits a malicious
website, that website could fetch from `localhost:5173`... no, that's not
how CORS works. The real issue: any developer's local environment that
happens to serve on `localhost:5173` is an allowed origin for the production
API. More importantly, if an attacker can get a victim to run a local server
on `localhost:5173` (e.g. via a dev tool), and the victim has active session
cookies for the production API, a page on that local server could make
authenticated API calls to production.

**Remediation:**
Remove the localhost origin from the production override. Local development
should use a separate `.env.dev` or a dev-specific compose file:

```yaml
# docker-compose.override.yaml:42-43
environment:
  - CORS_ORIGINS=https://cos.vollbuild.ch
```

---

### [MEDIUM] Email verification token passed in URL path (CWE-598, OWASP A07)

**Location:** `app/backend/vollbuild/api/auth/routes.py:601`
**Confirmed:** Yes

**Vulnerability:**
The email verification endpoint accepts the raw token as a URL path
parameter:

```python
# routes.py:601
@account_bp.get("/verify-email/<string:raw_token>")
def verify_email(raw_token: str):
    member = AccountService.verify_email(raw_token)
```

The verification URL is constructed with a fragment
(`routes.py:584`: `f".../verify-email#token={raw_token}"`), but the API
route expects the token in the **path** (`/verify-email/<raw_token>`). The
SPA extracts the fragment and calls `GET /api/v1/account/verify-email/{raw_token}`,
putting the token in the API request URL path. Path components are logged
in:

- Reverse proxy (Traefik/Caddy) access logs
- Backend application logs
- Browser history (for the API call URL)
- `Referer` headers if the verified page links to external resources

By contrast, the password reset flow correctly sends the token in the POST
body (`routes.py:307-314`), keeping it out of URLs.

**Impact:**
Token leakage via logs/browser history/Referer. Mitigated by: single-use
tokens (marked `used=True` on verification), 24-hour expiry, and 256-bit
entropy (`secrets.token_urlsafe(32)`). A leaked token is only useful if
intercepted before the legitimate user clicks it and within 24 hours.

**Remediation:**
Change the endpoint to accept the token in the POST body (matching the
password reset pattern):

```python
# routes.py — change to POST with body token:
@account_bp.post("/verify-email")
def verify_email():
    body = request.get_json(silent=True) or {}
    raw_token = body.get("token", "").strip()
    if not raw_token:
        return api_error("VALIDATION_ERROR", "token is required", 400)
    member = AccountService.verify_email(raw_token)
    db.session.commit()
    return jsonify({"ok": True, "verified": True}), 200
```

Update the frontend to POST the token instead of GET-ing the URL.

---

### [MEDIUM] Unpinned mutable image tags in mail stack (CWE-1104, OWASP A06)

**Location:** `docker-compose.mail.yml`
**Confirmed:** Yes

**Vulnerability:**
Several images use mutable tags instead of digest pins:

| Service       | Image                                  | Line |
| ------------- | -------------------------------------- | ---- |
| mongo         | `mongo:7`                              | 23   |
| certbot-init  | `certbot/dns-cloudflare:latest`        | 36   |
| certbot-renew | `certbot/dns-cloudflare:latest`        | 70   |
| mailserver    | `ghcr.io/zone-eu/wildduck:latest`      | 88   |
| socket-proxy  | `tecnativa/docker-socket-proxy:latest` | 188  |

The app services (caddy, postgres, redis, frontend, backend) are all
digest-pinned — good. But the mail stack services above will pull whatever
the tag currently points to on next `docker compose up`, with no guarantee
of integrity or compatibility.

**Impact:**
A supply-chain attack or breaking change to any of these images would be
silently pulled. The `socket-proxy` is particularly sensitive — it has
access to the Docker socket (scoped to `CONTAINERS=1, RESTART=1`, but still).

**Remediation:**
Pin all images by digest. Run `docker image inspect <image>:<tag> --format
'{{.RepoDigests}}'` to get the current digest, then pin:

```yaml
mongo:
  image: mongo:7@sha256:<digest>
certbot-init:
  image: certbot/dns-cloudflare:latest@sha256:<digest>
mailserver:
  image: ghcr.io/zone-eu/wildduck:latest@sha256:<digest>
socket-proxy:
  image: tecnativa/docker-socket-proxy:latest@sha256:<digest>
```

Use Renovate (already configured in `renovate.json`) to automate digest
updates with PR review.

---

### [LOW] Inventory self-instruction write gated by "read" permission (CWE-285, OWASP A01)

**Location:** `app/backend/vollbuild/api/inventory/routes.py` —
`POST /<item_id>/instructions/self`
**Confirmed:** Yes

**Vulnerability:**
The self-instruction endpoint (a write operation — a member adds an
instruction to an item for themselves) is gated by
`@permission_required("items", "read", ...)` — a **read** permission
authorizing a **write** action.

**Impact:**
A member who can only view inventory items can also create self-instructions.
Low impact (the instruction is scoped to the member themselves), but it
violates least-privilege: write actions should require write permissions.

**Remediation:**
Change the decorator to use a more appropriate permission (either
`items.update` or a dedicated `items.instruct_self` action):

```python
@inventory_bp.post("/<int:item_id>/instructions/self")
@permission_required("items", "instruct_self", "Add self-instruction for items")
```

Or, if all authenticated members should be able to do this, use
`@require_member`.

---

### [LOW] Money converted via float before Decimal storage (CWE-1339, OWASP A04)

**Location:** `app/backend/vollbuild/api/tiers/services.py:57-68`
**Confirmed:** Yes

**Vulnerability:**
`TierService.update` converts `price_chf` to `float` before assigning it to
the ORM field, which is `Numeric(10, 2)` (Decimal):

```python
# tiers/services.py:60-68
    if "price_chf" in data:
        val = data["price_chf"]
        if val is not None:
            try:
                price = float(val)       # ← float intermediate
                if price < 0:
                    raise_error(...)
                tier.price_chf = price   # ← stored to Numeric(10,2)
```

The same pattern applies to `percentage_value` and `coefficient` (line
103-107). The `Transaction.amount` and `Invoice.amount` fields correctly use
`Decimal` in their models (`Numeric(12, 2)`), but the tier service bypasses
this by converting to float first. `float("19.99")` becomes
`19.989999999999998` — PostgreSQL rounds to 2 decimals on storage, so the
final value is usually correct, but edge cases with more decimal places can
produce subtle rounding errors.

**Impact:**
Potential for subtle rounding errors in tier pricing. Low likelihood of
real-world impact (2-decimal precision absorbs most float artifacts), but
it's a correctness and integrity best-practice violation for financial data.

**Remediation:**
Use `Decimal` directly:

```python
from decimal import Decimal, InvalidOperation

    if "price_chf" in data:
        val = data["price_chf"]
        if val is not None:
            try:
                price = Decimal(str(val))
                if price < 0:
                    raise_error(400, "VALIDATION_ERROR", "price_chf must be non-negative")
                tier.price_chf = price
            except (TypeError, InvalidOperation):
                raise_error(400, "VALIDATION_ERROR", "price_chf must be a number")
        else:
            tier.price_chf = None
```

Apply the same pattern to `percentage_value` and `coefficient`.

---

### [LOW] Fernet key derived from SECRET_KEY when FERNET_KEY unset (CWE-321, OWASP A02)

**Location:** `app/backend/vollbuild/crypto.py:10-15`
**Confirmed:** Yes (documented legacy path)

**Vulnerability:**
When `FERNET_KEY` is not set, the Fernet encryption key is derived by
hashing `SECRET_KEY` with SHA-256:

```python
# crypto.py:10-15
def _get_key() -> bytes:
    fernet_key = current_app.config.get("FERNET_KEY")
    if fernet_key:
        return fernet_key.encode("utf-8")
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
```

This means:

- There is no key rotation story (changing `SECRET_KEY` breaks all encrypted
  codes).
- The same key is used for all encrypted codes (no per-purpose keys).
- If `SECRET_KEY` leaks, all encrypted codes are compromised (the Fernet key
  is deterministically derived from it).

**Impact:**
Low — this is the documented legacy path, and `.env.example` recommends
setting `FERNET_KEY` independently. In production with `FERNET_KEY` set
(`config.py:114`), this path is not reached. But if someone deploys without
setting `FERNET_KEY`, the encryption key is coupled to the session secret.

**Remediation:**
Make `FERNET_KEY` required in `ProductionConfig.validate()`:

```python
# config.py — ProductionConfig.validate():
    _require_env("SECRET_KEY")
    _require_env("JWT_SECRET_KEY")
    _require_env("DATABASE_URL")
    _require_env("FERNET_KEY")  # ← add this
```

This ensures production deployments cannot accidentally use the legacy
derivation.

---

### [LOW] GPG passphrase visible in process arguments (CWE-214, OWASP A05)

**Location:** `app/backend/vollbuild/services/backup.py:218-231`
**Confirmed:** Yes

**Vulnerability:**
The GPG encryption passphrase is passed as a command-line argument:

```python
# backup.py:218-231
gpg_cmd = [
    "gpg", "--batch", "--yes", "--quiet",
    "--passphrase", encryption_key,     # ← visible in /proc/<pid>/cmdline
    "--symmetric", "--cipher-algo", "AES256",
    "--output", gpg_path, dump_path,
]
```

Any process on the same host can read `/proc/<pid>/cmdline` and see the
passphrase. In a Docker container this is lower risk (PID namespace
isolation), but it's still a defense-in-depth concern — especially if the
container shares a PID namespace with others.

**Impact:**
Low in a containerized environment with PID isolation. Higher if PID
namespace is shared or if the host is multi-tenant.

**Remediation:**
Pass the passphrase via stdin instead of CLI args:

```python
gpg_cmd = [
    "gpg", "--batch", "--yes", "--quiet",
    "--passphrase-fd", "0",        # ← read passphrase from stdin (fd 0)
    "--symmetric", "--cipher-algo", "AES256",
    "--output", gpg_path, dump_path,
]
gpg_result = subprocess.run(
    gpg_cmd,
    input=encryption_key.encode(),
    capture_output=True,
    timeout=300,
)
```

Apply the same fix to the decrypt command at line 318-334.

---

### [LOW] i18n `/flagged` publicly exposes translation metadata; `/report` lacks permission check (CWE-200, CWE-285, OWASP A01)

**Location:** `app/backend/vollbuild/api/i18n/routes.py`
**Confirmed:** Yes

**Vulnerability:**

- `GET /i18n/<locale>/flagged` has no auth decorator — publicly exposes
  `needs_attention`/`is_missing`/`is_stale` flags for translations.
- `POST /i18n/<locale>/report` uses only `@jwt_required()` — any
  authenticated member can call it, no `permission_required` check.

**Impact:**
Low. The `/flagged` endpoint exposes translation completeness metadata (no
PII, no secrets). The `/report` endpoint allows any member to submit
translation issue reports (low abuse potential, but inconsistent with the
permission model).

**Remediation:**

- `/flagged`: Add `@jwt_required()` or leave public if translation status is
  intentionally public (document the decision).
- `/report`: Add `@permission_required("i18n", "report", "Report translation
issues")` or use `@require_member` if all members should be able to report.

---

### [LOW] CSP allows `'unsafe-inline'` for styles (CWE-79, OWASP A05)

**Location:** `app/deploy/Caddyfile:36`
**Confirmed:** Yes

**Vulnerability:**
The Content-Security-Policy header allows `'unsafe-inline'` for `style-src`:

```
style-src 'self' fonts.googleapis.com 'unsafe-inline'
```

This permits inline style attributes and `<style>` blocks, weakening the
CSP against style-based exfiltration attacks.

**Impact:**
Low. Mantine (the UI framework) uses CSS-in-JS and inline styles, so
`'unsafe-inline'` for styles may be required. Style-based data exfiltration
is possible but requires other vulnerabilities to inject the style.

**Remediation:**
If Mantine supports it, switch to a nonce-based CSP for styles. If not
possible with the current framework, document the limitation and ensure
`script-src` remains strict (`'self'` only, no `'unsafe-inline'` — which it
already is).

---

### [Informational] HSTS not set on frontend HTML by Caddy (CWE-319, OWASP A02)

**Location:** `app/deploy/Caddyfile:33-42` (no HSTS in Caddy header block);
set only by Flask `after_request` on API responses (`__init__.py:174-176`).
**Confirmed:** Yes

**Vulnerability:**
HSTS (`Strict-Transport-Security`) is set by the Flask `after_request` hook,
which only applies to API JSON responses (`/api/*`). The frontend HTML
served by Caddy does not include HSTS in its header block. TLS terminates at
the external Traefik, so HSTS should be set there — but that config is
outside this repo.

**Impact:**
A first-time visitor of the frontend HTML (before any API call) does not
receive HSTS, making them susceptible to SSL stripping on the first visit.

**Remediation:**
Add HSTS to the Caddyfile header block:

```
(header block in Caddyfile:34-42)
    Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
```

And verify that Traefik also sets HSTS on all responses (needs manual
verification on the host — see below).

---

### [Informational] Silent `except: pass` in after_request last_seen dispatch (CWE-390, OWASP A09)

**Location:** `app/backend/vollbuild/__init__.py:169-170`
**Confirmed:** Yes

**Vulnerability:**
The `_add_security_headers` after_request hook silently swallows all
exceptions from the last_seen dispatch:

```python
try:
    identity = get_jwt_identity()
    if identity is not None:
        _maybe_dispatch_last_seen(int(identity))
except Exception:
    pass  # unauthenticated request — skip last_seen update
```

**Impact:**
Low. Hides errors in the last_seen tracking (not security-critical, but can
mask Redis connectivity issues or Celery dispatch failures during
investigation).

**Remediation:**
Log at debug level instead of silent pass:

```python
except Exception:
    app.logger.debug("last_seen dispatch skipped", exc_info=True)
```

---

## Top 5 to fix first

Ordered by exploitability x impact:

1. **RBAC wildcard fallback** — affects every multi-resource blueprint.
   Any user with one resource's permission gets that action on all resources
   in the blueprint. Fix: remove the fallback in `permissions.py:229-239`.
   One-line change, high impact.

2. **Roles `is_admin` mass-assignment** — direct privilege escalation to
   admin for any user with role-update permission. Fix: add `is_admin`
   admin-only guard + call `filter_updatable_fields` in `roles/routes.py`.

3. **Settings revert without namespace check** — compounded by #1; allows
   non-admins to revert any setting. Fix: add `can_write` check in
   `revert_setting` (`settings/routes.py:131-149`).

4. **Redis unauthenticated** — if any container is breached, the broker and
   rate limiter are open. Fix: add `--requirepass` + update connection
   strings.

5. **CORS localhost in production** — remove `http://localhost:5173` from
   `docker-compose.override.yaml:43`.

---

## Categories that could NOT be fully assessed

| Category                        | What's needed                                                                                                                                                                                                                                                                                         |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Traefik config**              | The Traefik static config (`traefik.yml`), dynamic config, and TLS configuration are outside this repo. Need to verify: TLS version/cipher suite, HSTS on all responses, entrypoints, dashboard/API exposure, trusted-proxy/IP-spoofing prevention.                                                   |
| **CrowdSec**                    | The `crowdsec@file` middleware is referenced in labels but the CrowdSec bouncer config, acquisition config, and remediation rules are external. Need to verify: bouncer is actually enforcing (returns 403/429), real client IP is seen (not the Docker bridge IP), and remediations are appropriate. |
| **X-Forwarded-For trust chain** | `wsgi.py` uses ProxyFix (`Caddyfile` comments mention `x_for=2`). Need to verify on the host that the proxy chain is correctly configured so `request.remote_addr` reflects the real client IP (affects CrowdSec accuracy and rate-limit fairness).                                                   |
| **Runtime behaviour**           | This is a static audit. Dynamic testing (with authorization) would confirm: token expiry enforcement, session revocation propagation, rate-limit effectiveness under load, and Celery task argument visibility in Redis.                                                                              |
| **Git history**                 | Secrets may have been committed and removed in past commits. Recommend running `git log --all -p -- '*.env*' '**/secret*'` or a tool like `trufflehog`/`gitleaks` against the full history.                                                                                                           |

---

## Summary of good security practices observed

These are worth noting — the codebase has a solid security foundation in
several areas:

- **Password hashing:** argon2-cffi (argon2id) with zxcvbn strength
  enforcement (min 12 chars, score >= 3). No weak/home-rolled hashing.
- **Token security:** `secrets.token_urlsafe(32)` (256-bit) for all tokens;
  stored as SHA-256 hashes (not plaintext); single-use with expiry; timing
  dummy hash to prevent enumeration in forgot-password.
- **JWT cookies:** HttpOnly, Secure (in production), SameSite=Lax, CSRF
  protection enabled, session management with per-device tracking and
  revocation.
- **SQL injection:** All database queries use SQLAlchemy ORM constructs with
  bound parameters. `escape_like()` is used for LIKE patterns. No string
  interpolation in any `text()` call. No `eval`/`exec`/`pickle`/`yaml.load`
  in application code.
- **Celery serializer:** JSON (not pickle), `accept_content=["json"]` — no
  deserialization RCE vector.
- **SVG avatar sanitization:** nh3-based allowlist sanitization strips
  script/event handlers/foreignObject.
- **Container hardening:** `no-new-privileges:true` on all services; backend
  and frontend containers run as non-root users; digest-pinned images for
  core services; resource limits on all containers.
- **Error handling:** 500 errors return generic message; no verbose stack
  traces to clients. Security events (login, failed login, password change,
  admin actions) are audit-logged.
- **Env files:** `.env`, `.env.dev`, `app/frontend/.env` are all gitignored
  and not tracked in git (verified via `git ls-files`).
- **Frontend:** Source maps disabled in production build; only
  `VITE_API_BASE` exposed in the bundle (no secrets).
- **Dependencies:** `pip-audit` and `npm audit` both report 0
  vulnerabilities. Lock files are used for reproducible builds.
