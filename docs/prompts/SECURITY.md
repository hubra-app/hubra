Task: Full security assessment of the codebase (find & report vulnerabilities)

Role

Act as an application security engineer performing a defensive code audit of
our own application. Read the code, identify vulnerabilities, and report them so
we can fix them. This is a static review of a codebase we own — the goal is
remediation, not exploitation. Do NOT run destructive tests, exfiltrate data, or
produce weaponized exploits; describe impact and provide the fix.

Scope

The whole application: Flask/Python backend, Celery tasks, React frontend, and
the deployment/config surface (Docker Compose, Traefik, CrowdSec, env files,
CI config). Include infrastructure-as-code and configuration — misconfig is as
important as code bugs here.

Method


Work through the categories below (roughly OWASP Top 10 + ASVS-flavored).
For each finding, verify plausibility by reading the actual code path — don't
report a pattern match you haven't traced. Distinguish confirmed issues from
"needs manual verification."
Prioritize by real exploitability and blast radius, not by category.


What to look for

1. Broken access control / authorization (usually the highest-impact class)


Endpoints missing authentication or authorization checks, especially any that
slipped the RBAC auto-discovery/decorator registration.
Horizontal privilege escalation: can user A read/modify user B's resources by
changing an ID? (IDOR — check every route that takes an object id.)
Vertical escalation: can a Member/Supporter hit Core-only actions?
Mass-assignment: request payloads overwriting fields the user shouldn't control
(role, membership tier, is_admin, quotas).
Access decisions made only on the frontend with no server-side enforcement.
Direct object references in mail provisioning / settings / billing that don't
re-check ownership.


2. Injection


SQL injection: raw/interpolated SQL, unsafe use of text(), string-built
filters. Confirm parameterization.
Command injection: subprocess/os.system/shell calls with user-influenced
input (relevant if any task shells out to mail/PDF/QR tooling).
Template injection (SSTI) in Jinja if user input reaches template strings.
Header/log injection (CRLF) from unsanitized user input.
NoSQL/LDAP/other injection if any such store is queried.


3. Authentication & session security


Password storage via passlib with a strong scheme; no weak/home-rolled hashing.
Session cookies: HttpOnly, Secure, SameSite set appropriately; session
fixation on login; proper invalidation on logout/password change.
Token/OAuth (Authlib): state/nonce validation, token leakage, overly broad
scopes, missing expiry/rotation.
Password reset / email verification flows: token entropy, single-use, expiry,
no user enumeration in responses/timing.
MFA presence where warranted for admin/Core actions.


4. Secrets & cryptography


Hardcoded secrets, API keys, or credentials in code, config, or committed env
files; secrets in logs or error responses.
Fernet/PBKDF2 usage: key management (where does the master key live?), key
rotation story, correct KDF parameters, no reused/static salts/IVs.
Weak or misused crypto (ECB, static IV, MD5/SHA1 for security, random
instead of secrets for tokens).
TLS/cert handling: disabled verification anywhere (verify=False), SNI/host
mismatches.


5. Input validation & deserialization


Boundary validation with Pydantic before data reaches DB/external systems; flag
endpoints trusting raw request.json.
Insecure deserialization: pickle/yaml.load/eval/exec on untrusted input;
Celery pickle serializer on an exposed broker.
File uploads: type/size validation, path traversal in filenames, stored
outside webroot, not executable, content-type sniffing.


6. SSRF & unsafe outbound requests


User-controlled URLs/hosts in outbound calls (WildDuck/SMTP config, webhooks,
avatar/URL fetchers) that could hit internal services or cloud metadata.
Missing allowlists, timeouts, and redirect limits on outbound HTTP.


7. Sensitive data exposure & privacy


Secrets or internal config shipped in the frontend bundle (VITE_/REACT_APP_
values); production source maps served publicly.
PII in logs, error messages, or API responses beyond what's needed.
Member data protection: given Swiss revDSG/GDPR obligations for a Verein
handling member PII — data minimization, access scoping, and whether deletion/
export paths exist. Flag over-broad data returned by list/search endpoints.
Verbose stack traces / debug mode reachable in production.


8. CSRF


State-changing endpoints protected consistently with the auth scheme
(session-cookie flows need CSRF tokens; verify Flask-WTF/CSRF coverage).
CORS: flag * origins with credentials, overly permissive allowed origins,
reflected-origin bugs.


9. Security misconfiguration (infra & app)


Traefik: TLS config, exposed dashboards/API, correct trusted-proxy setup so
X-Forwarded-For can't be spoofed (also affects CrowdSec accuracy).
CrowdSec: bouncer actually enforcing; real client IP seen (not the proxy's).
Docker Compose: containers running as root, unnecessary port exposure,
secrets passed as build args or committed .env, missing resource limits,
writable/over-mounted volumes, latest tags.
Security headers: CSP, HSTS, X-Content-Type-Options, X-Frame-Options / frame
ancestors, Referrer-Policy.
Postgres: default/weak creds, exposed port, least-privilege DB user.
Redis broker: authenticated, not exposed, not shared with untrusted clients
(pickle + open Redis = RCE).


10. Dependencies & supply chain


Known-vulnerable dependencies (backend requirements/lockfile and frontend
package-lock). Recommend running pip-audit and npm audit and list any
criticals found.
Unpinned/unlocked dependencies; typosquat-risk or unmaintained packages.
Postinstall scripts / suspicious transitive packages.


11. Rate limiting & abuse / DoS


Auth-sensitive endpoints (login, reset, provisioning, invite) rate-limited at
the app layer to complement CrowdSec.
Unbounded operations: list/search without pagination, expensive queries, mail
fan-out (respect Infomaniak's 500/24h limit; broadcasts via the proper path).
Resource-exhaustion via large payloads / unbounded file uploads / zip bombs.


12. Business-logic vulnerabilities


Billing/invoicing: can amounts, references, or membership tiers be manipulated?
QR-bill/camt.054 parsing robust against forged/malformed input? Money as
Decimal (float bugs are a correctness+integrity issue).
Membership state machine: can dunning/expiry/tier transitions be bypassed?
Mail provisioning: can a user provision/forward to an address they don't own,
or escape the protected catchall?
Race conditions / TOCTOU on quota, uniqueness, or balance checks.


13. Logging, monitoring & error handling


Silent failure paths (except: pass) hiding security-relevant errors.
Security events (auth failures, authz denials, admin actions) logged for
detection; no secrets in those logs.
Errors returning internal detail to the client.


Output format

Group findings by severity (CVSS-style judgment), most severe first:


Critical — remote unauth RCE, auth bypass, injection with data access,
secret disclosure enabling takeover.
High — privilege escalation, IDOR exposing PII, stored XSS, SSRF to
internal services.
Medium — CSRF on meaningful actions, missing rate limits, weaker-than-ideal
crypto, misconfig with limited blast radius.
Low / Informational — hardening gaps, defense-in-depth, best-practice.


For each finding:

[Severity] <short title>  (CWE-###, OWASP A##)
Location: <file:lines or config path>
Confirmed: <yes / needs manual verification>
Vulnerability: <what it is and the exact code path that reaches it>
Impact: <what an attacker gains — realistic, not theoretical>
Remediation: <specific fix, with a code/config snippet>

End with:


Top 5 to fix first, ordered by exploitability × impact.
A short note on any category you could NOT assess and what's needed to.


Constraints


Defensive audit of our own code: report and remediate, do not produce working
exploits or perform live/destructive testing.
Trace each finding to real code before reporting; separate confirmed from
suspected to avoid false-positive noise.
Reference real files/lines/config; never invent them.
Prefer fixes using the existing stack; note where a dependency upgrade is the
actual fix.
Server-side is the security boundary; frontend findings are about secret/data
exposure and abuse-prevention, not "hiding code."
