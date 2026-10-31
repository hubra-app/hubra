"""Every encrypted value Hubra stores, for checking and re-encrypting them.

The columns encrypted with ``hubra.core.crypto`` live in each club schema
(``tenant_*``, including restore safety copies) and, for secret platform
settings, in ``public``.  ``check`` counts which key opens each value;
``rotate`` re-encrypts every value the current key does not open yet.
Neither ever changes a value no key opens.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

from sqlalchemy import inspect, text

from hubra.core.crypto import InvalidToken, decrypt_code, is_current, rotate_code
from hubra.core.extensions import db

# (table, primary key, encrypted column, extra WHERE)
COLUMNS: tuple[tuple[str, str, str, str], ...] = (
    ("codes", "id", "code", ""),
    ("internal_keys", "id", "value", ""),
    ("managed_mail_addresses", "id", "mailbox_password_encrypted", ""),
    ("platform_settings", "key", "value", " AND secret"),
)


@dataclass
class Report:
    current: int = 0
    old_key: int = 0
    unreadable: Counter = field(default_factory=Counter)
    rotated: int = 0

    @property
    def total(self) -> int:
        return self.current + self.old_key + sum(self.unreadable.values())

    @property
    def clean(self) -> bool:
        """True when the current key opens every stored value."""
        return not self.old_key and not self.unreadable


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _places() -> Iterator[tuple[str, str, str, str]]:
    """(qualified table, pk, column, where) for every place that exists."""
    bind = db.session.get_bind()
    if bind.dialect.name != "postgresql":
        tables = set(inspect(bind).get_table_names())
        for table, pk, col, where in COLUMNS:
            if table in tables:
                yield _q(table), pk, col, where
        return
    wanted = {(t, c): (pk, w) for t, pk, c, w in COLUMNS}
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
            yield f"{_q(schema)}.{_q(table)}", pk, col, where


def _walk(rotate: bool) -> Report:
    report = Report()
    for table, pk, col, where in list(_places()):
        rows = db.session.execute(
            text(
                f"SELECT {_q(pk)}, {_q(col)} FROM {table} "
                f"WHERE {_q(col)} IS NOT NULL AND {_q(col)} <> ''{where}"
            )
        ).all()
        for row_id, value in rows:
            if is_current(value):
                report.current += 1
                continue
            try:
                decrypt_code(value)
            except InvalidToken:
                report.unreadable[table] += 1
                continue
            report.old_key += 1
            if rotate:
                db.session.execute(
                    text(f"UPDATE {table} SET {_q(col)} = :v WHERE {_q(pk)} = :id"),
                    {"v": rotate_code(value), "id": row_id},
                )
                report.rotated += 1
        if rotate:
            db.session.commit()
    return report


def check() -> Report:
    return _walk(rotate=False)


def rotate() -> Report:
    return _walk(rotate=True)
