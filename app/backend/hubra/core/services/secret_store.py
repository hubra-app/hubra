"""Every encrypted value Hubra stores, for checking and re-encrypting them.

The encrypted columns live in each club schema (``tenant_*``, including
restore safety copies) and, for secret platform settings, in ``public``.
The club data keys (``data_keys.wrapped_key``) are themselves encrypted
with the master key.

``check`` counts which values are on the current keys; ``rotate`` rewraps
the data keys with the current master key and re-encrypts every value that
is not on its club's newest data key yet (older Fernet values included).
Neither ever changes a value no key opens.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

from sqlalchemy import inspect, text

from hubra.core import crypto
from hubra.core.extensions import db

# (table, primary key, encrypted column, extra WHERE)
COLUMNS: tuple[tuple[str, str, str, str], ...] = (
    ("codes", "id", "code", ""),
    ("internal_keys", "id", "value", ""),
    ("managed_mail_addresses", "id", "mailbox_password_encrypted", ""),
    ("platform_settings", "key", "value", " AND secret"),
)
_DATA_KEYS = ("data_keys", "id", "wrapped_key", "")


@dataclass
class Report:
    current: int = 0
    old_key: int = 0
    unreadable: Counter = field(default_factory=Counter)
    rotated: int = 0
    new_keys: int = 0

    @property
    def total(self) -> int:
        return self.current + self.old_key + sum(self.unreadable.values())

    @property
    def clean(self) -> bool:
        """True when every stored value is (now) on the current keys."""
        return self.old_key <= self.rotated and not self.unreadable


@dataclass(frozen=True)
class Place:
    table: str  # quoted, schema-qualified on Postgres
    pk: str
    column: str
    where: str
    purpose: str  # "<table>.<column>", bound into each value
    scope: str  # whose data key: c<tenant id> or p


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _places(spec=COLUMNS) -> Iterator[Place]:
    """Every place that exists, for the (table, pk, column, where) in *spec*."""
    bind = db.session.get_bind()
    if bind.dialect.name != "postgresql":
        tables = set(inspect(bind).get_table_names())
        for table, pk, col, where in spec:
            if table in tables:
                yield Place(
                    _q(table), pk, col, where, f"{table}.{col}", crypto.PLATFORM
                )
        return
    wanted = {(t, c): (pk, w) for t, pk, c, w in spec}
    rows = db.session.execute(
        text(
            "SELECT table_schema, table_name, column_name "
            "FROM information_schema.columns "
            "WHERE (table_schema = 'public' OR table_schema LIKE 'tenant\\_%') "
            "ORDER BY table_schema, table_name"
        )
    ).all()
    for schema, table, col in rows:
        if (table, col) in wanted:
            pk, where = wanted[(table, col)]
            yield Place(
                f"{_q(schema)}.{_q(table)}",
                pk,
                col,
                where,
                f"{table}.{col}",
                crypto.scope_of(schema),
            )


def _values(place: Place):
    return db.session.execute(
        text(
            f"SELECT {_q(place.pk)}, {_q(place.column)} FROM {place.table} "
            f"WHERE {_q(place.column)} IS NOT NULL AND {_q(place.column)} <> ''"
            f"{place.where}"
        )
    ).all()


def _update(place: Place, row_id, value: str) -> None:
    db.session.execute(
        text(
            f"UPDATE {place.table} SET {_q(place.column)} = :v WHERE {_q(place.pk)} = :id"
        ),
        {"v": value, "id": row_id},
    )


def _walk_data_keys(report: Report, rotate: bool) -> None:
    for place in _places((_DATA_KEYS,)):
        for row_id, wrapped in _values(place):
            if crypto.master_is_current(wrapped):
                report.current += 1
                continue
            try:
                new = crypto.rewrap(wrapped)
            except crypto.InvalidToken:
                report.unreadable[place.table] += 1
                continue
            report.old_key += 1
            if rotate:
                _update(place, row_id, new)
                report.rotated += 1
        if rotate:
            db.session.commit()


def _walk(rotate: bool, scopes: set[str] | None = None) -> Report:
    report = Report()
    if scopes is None:
        _walk_data_keys(report, rotate)
    for place in list(_places()):
        if scopes is not None and place.scope not in scopes:
            continue
        for row_id, value in _values(place):
            if crypto.is_current(value, place.scope):
                report.current += 1
                continue
            try:
                new = crypto.rotate_code(value, place.purpose, place.scope)
            except crypto.InvalidToken:
                report.unreadable[place.table] += 1
                continue
            report.old_key += 1
            if rotate:
                _update(place, row_id, new)
                report.rotated += 1
        if rotate:
            db.session.commit()
        else:
            db.session.rollback()  # a check never keeps a data key it made
    return report


def check() -> Report:
    return _walk(rotate=False)


def rotate() -> Report:
    return _walk(rotate=True)


def scopes_in_use() -> set[str]:
    """Every club (and the platform) that has stored values."""
    return {p.scope for p in _places()} | {crypto.PLATFORM}


def new_keys(scopes: set[str]) -> Report:
    """Give each scope a new data key version, then move its values onto it.

    Older versions stay, so older values in backups still open.
    """
    for scope in sorted(scopes):
        crypto.new_data_key(scope)
    db.session.commit()
    report = _walk(rotate=True, scopes=scopes)
    report.new_keys = len(scopes)
    return report
