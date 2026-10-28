"""
WSGI entry point.

Used by gunicorn in production:
    gunicorn --bind 0.0.0.0:5000 wsgi:app

And by flask CLI in development:
    flask run
"""

import os

from werkzeug.middleware.proxy_fix import ProxyFix

from hubra import create_app

app = create_app()
# One proxy hop for the API: external Traefik (edge) -> Flask.
# Caddy is NOT in the API path (it only fronts the frontend SPA on
# app.hubra.club); api.hubra.club routes directly Traefik -> backend:5000.
# x_for=1 trusts exactly one X-Forwarded-For entry so request.remote_addr is the
# real client IP — critical for CrowdSec (traefik middleware) and flask-limiter
# keying. Over-trusting (x_for=2) would let a spoofed header shift attribution.
# Behind a CDN that Traefik trusts (Cloudflare -> Traefik -> Flask) there are
# two hops: set PROXY_FIX_X_FOR=2 there and nowhere else.
x_for = int(os.environ.get("PROXY_FIX_X_FOR", "1"))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=x_for, x_proto=1, x_host=1)
