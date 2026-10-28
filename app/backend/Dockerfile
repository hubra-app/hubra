# Built from the repository root (like the frontends), because the image
# carries the plugins in plugins/ with their frontends built.

# ── Plugin frontends (npm run build:plugin, with the club app's toolchain) ──
FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS plugins
WORKDIR /src
COPY packages/api-client packages/api-client
COPY app/frontend/package.json app/frontend/package-lock.json app/frontend/
RUN cd app/frontend && npm ci
COPY app/frontend app/frontend
COPY plugins plugins
RUN cd app/frontend && npm run build:plugin

# ── API, Celery worker and beat ─────────────────────────────────────────────
FROM python:3.13-slim-bookworm@sha256:fcbd8dfc2605ba7c2eca646846c5e892b2931e41f6227985154a596f26ab8ed7

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY app/backend/requirements.lock app/backend/requirements.txt .
RUN pip install --no-cache-dir --no-deps -r requirements.lock

# PostgreSQL 16 client tools (pg_dump/pg_restore) + GnuPG for backup encryption.
# Bookworm ships PG 15 client which cannot dump from a PG 16 server.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg lsb-release \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail \
       https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" appuser

RUN mkdir -p /celerybeat && chown appuser:appuser /celerybeat

COPY app/backend/ .
# Plugins shipped with Hubra: available in the Marketplace, active once installed.
COPY --from=plugins /src/plugins /app/plugins

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "wsgi:app"]
