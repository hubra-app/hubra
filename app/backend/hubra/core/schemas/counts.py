"""Batch the per-row counts of list responses.

Some schemas show a count per row (members per group, votes per poll). Dumped
one row at a time, each count is its own query. ``prime_counts`` runs one
grouped query for a whole list and keeps each result on its row, where
``cached_count`` finds it; ``clear_counts`` drops them again after the dump so
a later dump in the same request counts afresh.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from sqlalchemy import func, select

from hubra.core.extensions import db


def prime_counts(rows: Iterable[Any], attr: str, column, *where) -> None:
    """Store on each row how many rows match ``column == row.id`` (and *where*)."""
    rows = list(rows)
    ids = [row.id for row in rows]
    counts: dict[int, int] = {}
    if ids:
        counts = dict(
            db.session.execute(
                select(column, func.count())
                .where(column.in_(ids), *where)
                .group_by(column)
            ).all()
        )
    for row in rows:
        row.__dict__[attr] = counts.get(row.id, 0)


def cached_count(obj: Any, attr: str, query: Callable[[], int | None]) -> int:
    """The primed count of *obj*, or run *query* when there is none."""
    count = obj.__dict__.get(attr)
    if count is None:
        count = query() or 0
    return count


def clear_counts(rows: Iterable[Any], *attrs: str) -> None:
    for row in rows:
        for attr in attrs:
            row.__dict__.pop(attr, None)
