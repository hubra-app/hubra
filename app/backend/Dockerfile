# Built from the repository root, like the frontends. No plugins are shipped:
# platform admins install them from the Marketplace (plugins.hubra.club).
#
# Two kinds of image (docs/platform-backend.md, "Images"):
#
#   target backend (the default): every file, HUBRA_ROLE unset (all). The one
#     image of a Compose install.
#   target role, --build-arg ROLE=app|global|platform: only the hubra modules
#     that role imports (scripts/role_files.py), with HUBRA_ROLE set to it, so
#     every process started from it (API, worker, beat, init step) is that
#     role. images.yml publishes app-backend, global-backend, platform-backend.

# ── Shared base: Python packages and system tools ──────────────────────────
FROM python:3.13-slim-bookworm@sha256:fcbd8dfc2605ba7c2eca646846c5e892b2931e41f6227985154a596f26ab8ed7 AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY app/backend/requirements.lock app/backend/requirements.txt .
RUN pip install --no-cache-dir --no-deps --require-hashes -r requirements.lock

# PostgreSQL client tools (pg_dump/pg_restore) from the PGDG repo + GnuPG/age
# for backup encryption. pg_dump refuses a server with a newer major version
# than its own, so every supported server major gets its client, side by side
# in /usr/lib/postgresql/<major>/bin; backups pick the one matching the server
# (hubra/core/services/pg_tools.py). tests/test_pg_tools.py checks that the
# Postgres images in docker-compose.yml and deploy/ are covered.
# Pango is what WeasyPrint draws invoice PDFs with, and Liberation Sans is a
# font the Swiss QR bill allows (the slim image has no fonts at all).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg age lsb-release \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-liberation \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail \
       https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       postgresql-client-16 postgresql-client-17 postgresql-client-18 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" appuser

RUN mkdir -p /celerybeat /var/lib/hubra/files \
    && chown appuser:appuser /celerybeat /var/lib/hubra/files

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "wsgi:app"]

# ── One role's files ─────────────────────────────────────────────────────────
FROM base AS role-files
ARG ROLE
COPY app/backend/ /src/
RUN test -n "$ROLE" \
    && python /src/scripts/role_files.py "$ROLE" --root /src --prune \
    && rm -rf /src/scripts /src/tests

# ── One role's image: app-backend, global-backend, platform-backend ─────────
FROM base AS role
ARG ROLE
COPY --from=role-files /src/ /app/
ENV HUBRA_ROLE=${ROLE}
ARG GIT_SHA=""
ENV HUBRA_GIT_SHA=${GIT_SHA}
USER appuser

# ── Every file, every role (Compose; the default target) ────────────────────
FROM base AS backend
COPY app/backend/ .

# The commit this image was built from (images.yml passes it). Manage shows it
# under Diagnose; empty means a local build, shown as "dev". Last, so a new
# commit does not invalidate the cached layers above.
ARG GIT_SHA=""
ENV HUBRA_GIT_SHA=${GIT_SHA}

USER appuser
