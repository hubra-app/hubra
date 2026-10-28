Review and harden the public-facing membership application endpoint (the applications blueprint) against abuse — this is a distinct attack surface from the authenticated-user rate limiting already covered in the security remediation, since this endpoint is reachable by anyone without an account.

## Step 1 — Investigate current state

1. Locate the public application submission endpoint and confirm it requires no authentication:
   grep -n "require_permission\|jwt_required" app/backend/vollbuild/api/applications/routes.py
2. Check if any rate limiting, CAPTCHA, or bot protection already exists on this specific endpoint (separate from the auth endpoints covered earlier):
   grep -n "limiter\|captcha\|honeypot" app/backend/vollbuild/api/applications/routes.py
3. Check what happens after an application is submitted — does it immediately create a pending record visible to admins, or does it require email verification first? This matters because without verification, someone could spam applications using OTHER people's real email addresses, which is both abusive and potentially harassing to those third parties.

## Step 2 — Implement protections

1. Add rate limiting via the flask-limiter setup already established in the auth security work (e.g. 3-5 submissions per hour per IP) — reuse the existing limiter instance/config rather than creating a new one.
2. Add a honeypot field (a hidden form field real users won't fill in, but bots scraping/auto-filling forms typically will) as a lightweight bot deterrent without the UX cost of a CAPTCHA — propose this as the first line of defense given it's free and low-friction.
3. If honeypot proves insufficient in practice (flag as a "if needed later" item, don't over-engineer day one), propose adding a CAPTCHA (hCaptcha or Cloudflare Turnstile, both privacy-friendlier than reCAPTCHA) as a follow-up.
4. Implement (or confirm existing) email verification BEFORE an application enters the admin review queue — i.e. the applicant must click a confirmation link sent to the email they provided, proving they control that address, before an admin sees it as a real pending application. If this doesn't exist yet, treat it as the most important fix in this prompt, more important than rate limiting/CAPTCHA, since it directly prevents third-party email abuse.

## Step 3 — Verify and report

Test the rate limit triggers correctly, confirm the honeypot field doesn't appear in the rendered form (or appears but is hidden/styled to be invisible to real users) and rejects submissions where it's filled, and confirm the email verification gate works end-to-end (submit → email sent → click link → THEN admin sees it in the queue, not before).
