Split the Flask backend API to a dedicated subdomain (api.vollbuild.ch), with full security-focused CORS configuration, correct cross-origin header handling, and JWT cookie adjustments. TLS termination and frontend HTTPS are handled by an EXTERNAL Traefik container already managing the stack (defined outside this project's compose files) — do not attempt to manage TLS certs for api.vollbuild.ch within this project.

## Step 1 — Investigate current state before changing anything

1. Confirm the current domain/routing setup — specifically how the external Traefik container currently routes traffic to this stack:
   cat compose.override.yml | grep -A 30 "traefik\|labels\|rule\|Host"

2. Confirm the frontend Docker network shared with the external Traefik (visible in compose.override.yml as "frontend: external: true" from earlier in this conversation — confirm it's still correct and the backend is NOT currently on this network, since it was only reached via Caddy proxy):
   docker network ls | grep frontend
   docker network inspect frontend | grep -i "community-backend\|community-caddy"

3. Confirm exactly how the frontend currently reaches the backend — relative path (/api proxied by Caddy) or absolute URL:
   grep -rn "VITE_API_BASE\|API_BASE" app/frontend/src/ app/frontend/.env*docker-compose*.yml compose*.yml 2>/dev/null

4. Show the full current Caddyfile to understand what Caddy currently proxies:
   cat app/deploy/Caddyfile

5. Confirm the current CORS configuration in Flask:
   grep -rn "CORS\|cors\|CORS_ORIGIN" app/backend/vollbuild/ --include="*.py"
   grep -n "CORS_ORIGIN\|CORS" .env docker-compose*.yml compose*.yml 2>/dev/null

6. Confirm the current JWT cookie settings — SameSite, Secure, Domain — since moving to a separate subdomain directly affects cookie behavior:
   grep -rn "JWT_COOKIE\|SAMESITE\|cookie_domain" app/backend/vollbuild/ --include="*.py"
   grep -n "JWT_COOKIE" .env docker-compose*.yml 2>/dev/null

7. Check every frontend file that constructs or references an API URL — this determines the full scope of frontend changes needed:
   grep -rn "fetch(\|axios\|/api/" app/frontend/src/ --include="*.tsx" --include="*.ts" | grep -v node_modules | head -30

8. Check whether flask-cors is already installed:
   grep -n "flask-cors\|Flask-Cors" app/backend/requirements*.txt

9. Check what currently hits the backend URL directly (health checks, monitoring, CI) so these can be updated after the move:
   grep -rn "backend:5000\|localhost:5000\|api/v1/health" docker-compose*.yml compose*.yml .gitlab-ci.yml 2>/dev/null

Report all findings before proceeding — especially: (a) confirm the frontend network name shared with external Traefik, (b) confirm VITE_API_BASE is currently a relative /api path (meaning ALL API calls currently go through Caddy), and (c) confirm the exact current production frontend URL (cos.public.reyki.net vs vollbuild.ch vs both) since this is the critical input to the CORS allowed-origins list and the JWT cookie domain decision.

## Step 2 — Design decisions (confirm ALL before implementing)

### 2.1 Subdomain and DNS

Add an A record for api.vollbuild.ch in Cloudflare pointing to the VPS public IP:
   curl -s ifconfig.me

Confirm the IP, then add the DNS record manually in Cloudflare (or via the Cloudflare API if you have automation set up) before any other steps — Traefik needs the DNS to resolve before it can provision the TLS certificate for api.vollbuild.ch via its own ACME integration.

### 2.2 TLS — Traefik's responsibility, not this stack's

The external Traefik container handles TLS termination for all HTTP/HTTPS traffic. When the backend container is added to the shared frontend Docker network with the correct Traefik labels, Traefik will automatically provision a Let's Encrypt certificate for api.vollbuild.ch via its configured ACME resolver (the same one already handling cos.public.reyki.net). Confirm the ACME resolver name used by the external Traefik:
   docker inspect <traefik_container_name> | grep -A 5 "certresolver\|acme"

# or check the external Traefik's config file/labels

This resolver name is needed for the backend's Traefik labels (certresolver=<name>). The existing labels in compose.override.yml use "letencrypt" (note: confirm the spelling — "letencrypt" vs "letsencrypt" — this matters exactly, since a typo here silently falls back to HTTP):
   grep "certresolver" compose.override.yml

### 2.3 Routing: what Traefik handles vs what Caddy handles after the split

**Before the split:**

- Traefik → Caddy → (frontend React app served by Caddy, /api/* proxied by Caddy to backend)

**After the split:**

- Traefik → Caddy → (frontend React app only, no more /api/* proxying)
- Traefik → backend directly (via api.vollbuild.ch)

This means:

1. The /api reverse_proxy block in the Caddyfile can be REMOVED — the frontend will call api.vollbuild.ch directly, not route through Caddy for API calls.
2. The backend container needs to be added to the external frontend Docker network so Traefik can reach it directly.
3. The backend container gets its own Traefik labels for api.vollbuild.ch routing.

Confirm: are there any internal services (other containers in this stack) that currently call the backend via Caddy's /api path (rather than directly via <http://backend:5000>)? If so, those also need updating to call backend:5000 directly after Caddy's proxy rule is removed.
   grep -rn "<http://caddy\|/api/>" docker-compose*.yml compose*.yml app/backend/ 2>/dev/null | grep -v ".pyc"

### 2.4 JWT cookie domain — the most critical decision

Moving the API to api.vollbuild.ch while the frontend stays on vollbuild.ch (or cos.public.reyki.net) creates a cross-origin cookie problem. A cookie set by api.vollbuild.ch is NOT automatically sent by the browser with requests to api.vollbuild.ch from a different origin unless the cookie's Domain attribute is correctly set.

This depends entirely on the production frontend domain — which must be confirmed before anything else:

**Case A: Production frontend runs on vollbuild.ch or any subdomain of it (e.g. app.vollbuild.ch)**
Set JWT_COOKIE_DOMAIN = .vollbuild.ch (leading dot means "this domain and all subdomains"). The browser will then send the cookie from vollbuild.ch to api.vollbuild.ch, same registrable domain. This is the clean, correct approach.

**Case B: Production frontend runs on cos.public.reyki.net (a completely different registrable domain from vollbuild.ch)**
Cookie domain sharing is IMPOSSIBLE across different registrable domains — this is a hard browser security boundary. In this case the options are:
(a) Move the production frontend to vollbuild.ch (or a subdomain of it) — eliminates the problem entirely, and probably makes sense long-term regardless since vollbuild.ch is the actual club's domain
(b) Switch from HttpOnly cookies to Authorization header tokens stored in memory (NOT localStorage — that's XSS-vulnerable) — valid approach for cross-domain APIs but requires more client-side state management than cookies
(c) Add a same-domain API proxy to the frontend's Caddy/Traefik setup that makes api.vollbuild.ch requests appear same-origin to the browser — essentially the split is frontend-visible only via DNS/TLS, not truly cross-origin in the browser's view

**Confirm which case applies before implementing anything else.** This is the single most consequential design question in this whole prompt — getting it wrong means either authentication silently breaks (cookies not sent cross-domain) or a security regression (moving away from HttpOnly cookies unnecessarily).

### 2.5 SameSite reconsideration

Regardless of Case A or B above, SameSite must be reconsidered. The current SameSite=Strict setting means cookies are only sent for same-site navigations. Once the API is on api.vollbuild.ch, requests from vollbuild.ch to api.vollbuild.ch are considered cross-site by strict SameSite rules in most browsers, even though they share the same registrable domain.

Propose changing to SameSite=Lax, which allows cookies to be sent in cross-subdomain requests initiated by the frontend while still blocking most CSRF vectors — combined with the existing CSRF double-submit token from the earlier security work (which remains as the actual CSRF protection mechanism, with SameSite=Lax as a defense-in-depth layer rather than the primary control). Confirm this trade-off is acceptable.

### 2.6 CORS configuration — exact requirements

Once the domain situation (Step 2.4) is resolved, implement CORS in Flask (not at Traefik/Caddy level — Flask-level CORS is version-controlled, code-reviewable, and doesn't silently change with infrastructure changes):

```python
from flask_cors import CORS

CORS(
    app,
    origins=allowed_origins,              # Explicit list, NEVER wildcard (*)
    supports_credentials=True,            # Required for JWT cookies cross-origin
    allow_headers=[
        "Content-Type",
        "X-CSRF-Token",                   # JWT cookie CSRF protection
        "X-Access-Token",                 # WildDuck API token if proxied
    ],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    expose_headers=[
        "Content-Disposition",            # QR-bill PDF download filenames
        "X-Total-Count",                  # Paginated list responses
    ],
    max_age=600,                          # 10 min preflight cache
)
```

CORS_ORIGINS in .env: comma-separated list of exact allowed origins:
   Production: CORS_ORIGINS=<https://vollbuild.ch,https://cos.public.reyki.net>
   Development: CORS_ORIGINS=<https://vollbuild.ch,https://cos.public.reyki.net,http://localhost:5173>

Critical: supports_credentials=True (required for cookie sending) MUST be combined with explicit origins — flask-cors will raise an error or silently fail if you combine supports_credentials=True with origins="*". Never use wildcard with credentials. Confirm this constraint is understood.

### 2.7 Security response headers

Add to Flask app factory via after_request hook (NOT in Traefik middleware, for the same reviewability reason as CORS):

```python
@app.after_request
def add_security_headers(response):
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
```

Do NOT add Content-Security-Policy here — CSP applies to HTML documents, not JSON API responses. CSP belongs on the frontend (Caddy response headers for the React app), not the API.

## Step 3 — Implementation (only after ALL Step 2 decisions confirmed)

### 3.1 DNS

Add api.vollbuild.ch A record in Cloudflare pointing to the VPS IP. Wait for propagation (fast with Cloudflare, typically under 1 minute) before testing.

### 3.2 compose.override.yml changes

Add the backend service to the external frontend network and add Traefik labels:

```yaml
backend:
  networks:
    - cos_internal
    - frontend           # ADD: so Traefik can route to it directly
  labels:
    - "traefik.enable=true"
    - "traefik.docker.network=frontend"
    - "traefik.http.routers.cos-api-secure.rule=Host(`api.vollbuild.ch`)"
    - "traefik.http.routers.cos-api-secure.entrypoints=websecure"
    - "traefik.http.routers.cos-api-secure.tls.certresolver=letencrypt"  # confirm spelling
    - "traefik.http.services.cos-api-secure.loadbalancer.server.port=5000"
    - "traefik.http.routers.cos-api-secure.middlewares=crowdsec@file,error-pages-middleware"
```

Update environment variables:

```yaml
environment:
  CORS_ORIGINS: "https://vollbuild.ch,https://cos.public.reyki.net"
  JWT_COOKIE_DOMAIN: ".vollbuild.ch"    # only if Case A confirmed in Step 2.4
  JWT_COOKIE_SAMESITE: "Lax"            # changed from Strict
```

### 3.3 Caddyfile changes

Remove the /api/* reverse_proxy block — confirm this is the ONLY change needed and no other services rely on Caddy for backend proxying before removing it.

### 3.4 Flask CORS and security headers

Implement CORS and security headers in the Flask app factory per Step 2.6 and 2.7. Update config.py to parse CORS_ORIGINS as a list:

```python
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "").split(",")
    if o.strip()
]
```

Update JWT cookie config:

```python
JWT_COOKIE_DOMAIN = os.environ.get("JWT_COOKIE_DOMAIN", None)
JWT_COOKIE_SAMESITE = os.environ.get("JWT_COOKIE_SAMESITE", "Lax")
```

### 3.5 Frontend changes

1. Update VITE_API_BASE in compose.override.yml (frontend service):

```yaml
environment:
  VITE_API_BASE: "https://api.vollbuild.ch/api"
```

1. Ensure every fetch/axios call includes credentials: "include" — without this the browser will not send the JWT cookie cross-origin even if everything else is correctly configured:
   grep -rn "fetch(" app/frontend/src/api/ --include="*.ts" --include="*.tsx" | grep -v "credentials"

   Any call missing credentials: "include" must be updated. Find the central fetch wrapper/interceptor (likely one file in api/) and add it there rather than updating every call individually:
   grep -rln "fetch\|axios" app/frontend/src/api/ --include="*.ts" | head -5

2. Rebuild the frontend with the new VITE_API_BASE:
   docker compose build frontend
   docker compose up -d frontend

### 3.6 Update internal references

Update anything currently referencing the old internal backend URL that now needs to use the external api.vollbuild.ch or the direct internal backend:5000 address:

- Uptime Kuma health checks: update the monitored URL to <https://api.vollbuild.ch/api/v1/health>
- GitLab CI: update any API URL references
- Any internal service making HTTP calls to the backend via Caddy's /api path

## Step 4 — Verify

1. Confirm Traefik provisioned the TLS cert for api.vollbuild.ch:
   echo | openssl s_client -connect api.vollbuild.ch:443 -servername api.vollbuild.ch 2>/dev/null | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"

2. Confirm the API is reachable on the new subdomain:
   curl -s <https://api.vollbuild.ch/api/v1/health> | python3 -m json.tool

3. Confirm CORS headers are correctly returned for a preflight request from the allowed origin:
   curl -s -X OPTIONS <https://api.vollbuild.ch/api/v1/health> \
     -H "Origin: <https://cos.public.reyki.net>" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -v 2>&1 | grep -i "access-control\|allow"

4. Confirm wildcard CORS is NOT being returned (critical security check):
   curl -s -X OPTIONS <https://api.vollbuild.ch/api/v1/health> \
     -H "Origin: <https://evil.attacker.com>" \
     -v 2>&1 | grep -i "access-control-allow-origin"
   This should return nothing or the exact evil.attacker.com origin should NOT appear in the response.

5. Confirm JWT cookie is set with correct Domain, SameSite, Secure attributes after login:
   curl -s -X POST <https://api.vollbuild.ch/api/v1/auth/login> \
     -H "Content-Type: application/json" \
     -d '{"email":"<test@vollbuild.ch>","password":"testpass"}' \
     -v 2>&1 | grep -i "set-cookie"
   Confirm: HttpOnly present, Secure present, SameSite=Lax, Domain=.vollbuild.ch (or whatever was confirmed in Step 2.4)

6. Confirm the full authenticated flow works end-to-end from the browser: log in, confirm cookie is sent with subsequent API requests to api.vollbuild.ch, confirm an authenticated endpoint returns data correctly.

7. Confirm the old Caddy /api/* path no longer works (returns 404 or connection refused, not a proxy to the backend):
   curl -s <https://cos.public.reyki.net/api/v1/health>
   This should now fail (or return a 404 from Caddy) rather than proxying to the backend.

8. Confirm security headers on API responses:
   curl -s <https://api.vollbuild.ch/api/v1/health> -v 2>&1 | grep -i "strict-transport\|x-content-type\|x-frame\|referrer"

9. Run the full test suite — confirm nothing broke due to CORS/cookie domain changes:
   docker compose exec -T backend python -m pytest -ra

## Step 5 — Report

Confirm: which Case (A or B) was confirmed for the cookie domain situation, the exact CORS_ORIGINS list applied, the Traefik certresolver name used, that Caddy's /api proxy block was removed and confirmed no internal services depended on it, and that the end-to-end authenticated browser flow works correctly on the new subdomain.

Wait for my confirmation on ALL Step 2 decisions — especially the JWT cookie domain Case (A vs B, Step 2.4) — before any implementation begins. This is the single most consequential decision in this prompt and getting it wrong silently breaks authentication for all users.
