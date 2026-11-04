"""Run a start-up command while holding a Postgres advisory lock.

    python -m hubra.core.startup_lock sh -c "flask db upgrade && flask seed ..."

The API's init step (migrations, permission sync, seeds, plugin sync)
must not run twice at the same time, which happens as soon as two API
pods or containers start together.  This waits for the lock, runs the
command, and releases the lock when it ends (Postgres also drops it if
this process dies).  Without a Postgres ``DATABASE_URL`` it just runs the
command.

Compose starts this as soon as the Postgres container runs, which on a
fresh volume is before the database takes connections (the image sets the
database up first, then restarts the server).  So the first connection is
retried for up to CONNECT_WAIT seconds.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time

from hubra.core.plugins.reload import _database_url

# "hubra-init" as ASCII bytes; distinct from the migration and plugin keys.
LOCK_KEY = 0x68756272612D696E

# How long to wait for Postgres to take connections, in seconds.
CONNECT_WAIT = 90

_log = logging.getLogger("hubra.startup_lock")


def run(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: python -m hubra.core.startup_lock COMMAND [ARGS...]",
            file=sys.stderr,
        )
        return 2
    url = _database_url()
    if not url.startswith("postgresql"):
        return subprocess.call(argv)

    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    engine = create_engine(url, poolclass=NullPool)
    with _connect(engine) as conn:
        print("startup_lock: waiting for the init lock", file=sys.stderr, flush=True)
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": LOCK_KEY})
        conn.commit()
        print("startup_lock: got it", file=sys.stderr, flush=True)
        try:
            return subprocess.call(argv)
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
            conn.commit()


def _connect(engine, wait: float = CONNECT_WAIT):
    """The first connection, retried while Postgres is not up yet."""
    from sqlalchemy.exc import OperationalError

    deadline = time.monotonic() + wait
    while True:
        try:
            return engine.connect()
        except OperationalError:
            if time.monotonic() >= deadline:
                raise
            print("startup_lock: database not up yet, retrying", file=sys.stderr, flush=True)
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
