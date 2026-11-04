"""One Postgres database per pytest-xdist worker.

The tests wipe every table between tests, so workers sharing one database
would wipe each other's data. Worker gw1 uses <database>_gw1, created empty
when it is missing (the role needs CREATEDB).
"""

from __future__ import annotations

import os


def database_for_worker(url: str) -> str:
    """The test database URL for this worker (unchanged without -n or Postgres)."""
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker or not url.startswith("postgresql"):
        return url

    import psycopg2
    from sqlalchemy.engine import make_url

    base = make_url(url)
    mine = base.set(database=f"{base.database}_{worker}")
    conn = psycopg2.connect(
        host=base.host,
        port=base.port or 5432,
        user=base.username,
        password=base.password,
        dbname=base.database,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (mine.database,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{mine.database}"')
    finally:
        conn.close()
    return mine.render_as_string(hide_password=False)
