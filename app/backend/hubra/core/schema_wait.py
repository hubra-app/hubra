"""Wait until the database schema is at least as new as this image's code.

    python -m hubra.core.schema_wait [--timeout SECONDS]

In a split install (docs/platform-backend.md) only the platform backend
runs the init step (``flask db upgrade``, permission sync, seeds, plugin
sync). The club backend's start-up waits here instead, so a club pod
never serves new code against an old schema:

- the database has this image's Alembic heads, or newer revisions this
  image doesn't know (the platform runs a newer release): go.
- the database is behind: wait, and exit 1 after ``--timeout`` seconds.
  On Kubernetes the old club pod keeps serving meanwhile, so a club
  release that is ahead of the platform release just doesn't roll out.

Without a Postgres ``DATABASE_URL`` (SQLite in development) it returns at
once.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from hubra.core.plugins.reload import _database_url

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def _log(message: str) -> None:
    print(f"schema_wait: {message}", file=sys.stderr, flush=True)


def status(script, current: set[str]) -> str:
    """``ready``, ``ahead`` (the database is newer) or ``behind``."""
    heads = set(script.get_heads())
    if not current:
        return "behind"
    known: set[str] = set()
    for rev in current:
        try:
            if script.get_revision(rev) is None:
                return "ahead"
        except Exception:  # alembic raises for a revision it doesn't know
            return "ahead"
        known.add(rev)
    # Every head of this image is applied when it is one of the current
    # revisions or below one of them.
    applied: set[str] = set()
    for rev in known:
        applied.update(r.revision for r in script.iterate_revisions(rev, "base"))
    return "ready" if heads <= applied else "behind"


def _current_revisions(engine) -> set[str]:
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT version_num FROM alembic_version"))
            return {row[0] for row in rows}
    except Exception as exc:  # no table yet, or the database is starting
        _log(f"cannot read alembic_version yet ({exc.__class__.__name__})")
        return set()


def run(timeout: float, interval: float = 5.0) -> int:
    url = _database_url()
    if not url.startswith("postgresql"):
        _log("no Postgres DATABASE_URL, nothing to wait for")
        return 0

    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    script = ScriptDirectory(str(MIGRATIONS))
    engine = create_engine(url, poolclass=NullPool)
    deadline = time.monotonic() + timeout
    said = False
    while True:
        state = status(script, _current_revisions(engine))
        if state == "ready":
            _log("schema is up to date")
            return 0
        if state == "ahead":
            _log("schema is newer than this image (platform runs a newer release); ok")
            return 0
        if not said:
            _log(
                "schema is older than this image; waiting for the platform "
                "backend to migrate (heads: " + ", ".join(sorted(script.get_heads())) + ")"
            )
            said = True
        if time.monotonic() >= deadline:
            _log(
                f"gave up after {int(timeout)}s: deploy the platform backend "
                "on this release (or newer) first"
            )
            return 1
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hubra.core.schema_wait")
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("SCHEMA_WAIT_TIMEOUT", 900)),
        help="seconds to wait before giving up (default 900)",
    )
    args = parser.parse_args(argv)
    return run(args.timeout)


if __name__ == "__main__":
    sys.exit(main())
