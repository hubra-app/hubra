FROM python:3.13-slim-bookworm@sha256:fcbd8dfc2605ba7c2eca646846c5e892b2931e41f6227985154a596f26ab8ed7

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.lock requirements.txt .
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

COPY . .

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "wsgi:app"]
