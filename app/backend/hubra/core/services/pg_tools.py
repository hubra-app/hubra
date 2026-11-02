"""Pick the pg_dump / pg_restore that fits the database server.

pg_dump refuses to dump a server with a newer major version than its own
("aborting because of server version mismatch").  The backend image therefore
installs several PostgreSQL client versions side by side (Debian puts them in
``/usr/lib/postgresql/<major>/bin``), and backups use the one that matches the
server's major version, or the closest newer one.

Without that directory (a developer machine, the test suite on SQLite) the
tool on ``PATH`` is used as before.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from sqlalchemy import text

from hubra.core.extensions import db

# Overridable for tests and for installs that put the clients elsewhere.
PG_LIB_DIR = os.environ.get("HUBRA_PG_LIB_DIR", "/usr/lib/postgresql")


class ClientTooOld(RuntimeError):
    """The server's major version is newer than every installed client."""


def installed_majors(lib_dir: str | None = None) -> list[int]:
    """Major versions with a client in ``<lib_dir>/<major>/bin``, ascending."""
    lib_dir = lib_dir or PG_LIB_DIR
    try:
        names = os.listdir(lib_dir)
    except OSError:
        return []
    majors = []
    for name in names:
        if re.fullmatch(r"\d+", name) and os.access(
            os.path.join(lib_dir, name, "bin", "pg_dump"), os.X_OK
        ):
            majors.append(int(name))
    return sorted(majors)


def server_major() -> int | None:
    """The database server's major version, or None when it is not Postgres."""
    if db.engine.dialect.name != "postgresql":
        return None
    num = db.session.execute(text("SHOW server_version_num")).scalar()
    return int(num) // 10000


def pick_major(server: int | None, majors: list[int]) -> int | None:
    """The client major to use for ``server``: the same, else the closest newer.

    None means "use the tool on PATH" (no versioned clients installed, or the
    server version is unknown).  Raises ClientTooOld when every installed
    client is older than the server.
    """
    if not majors or server is None:
        return None
    fitting = [m for m in majors if m >= server]
    if not fitting:
        raise ClientTooOld(
            f"The database server runs PostgreSQL {server}, but the newest "
            f"pg_dump in the backend image is {max(majors)}. pg_dump cannot "
            "back up a newer server: update the backend image (it installs "
            "postgresql-client-<major>) or run the server version it supports."
        )
    return min(fitting)


def tool(name: str, server: int | None = None, lib_dir: str | None = None) -> str:
    """Path of ``name`` (pg_dump, pg_restore) for a server of major ``server``."""
    lib_dir = lib_dir or PG_LIB_DIR
    major = pick_major(server, installed_majors(lib_dir))
    if major is None:
        return name
    return os.path.join(lib_dir, str(major), "bin", name)


def newest(name: str, lib_dir: str | None = None) -> str:
    """The newest installed ``name``; it reads archives from any older pg_dump."""
    lib_dir = lib_dir or PG_LIB_DIR
    majors = installed_majors(lib_dir)
    if not majors:
        return name
    return os.path.join(lib_dir, str(majors[-1]), "bin", name)


@dataclass
class Status:
    server_major: int | None
    client_majors: list[int]
    client_major: int | None
    ok: bool
    error: str | None


def status() -> Status:
    """Which client a backup would use right now, for the Backups page and CLI."""
    majors = installed_majors()
    try:
        server = server_major()
    except Exception as exc:  # database down: say so, don't break the page
        return Status(None, majors, None, False, f"Database not reachable: {exc}")
    try:
        chosen = pick_major(server, majors)
    except ClientTooOld as exc:
        return Status(server, majors, None, False, str(exc))
    return Status(server, majors, chosen, True, None)
