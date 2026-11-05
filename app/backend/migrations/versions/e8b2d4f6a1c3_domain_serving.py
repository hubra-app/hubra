"""Custom domains: serving state

Public schema. A verified club domain gets its own Ingress and certificate
(hubra.core.services.domain_serving); these columns hold how far that got.

Revision ID: e8b2d4f6a1c3
Revises: d5a7c3e9f1b4
Create Date: 2026-11-05 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e8b2d4f6a1c3"
down_revision = "d5a7c3e9f1b4"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("serving_status", sa.String(20)),
    ("serving_error", sa.String(500)),
    ("serving_checked_at", sa.DateTime(timezone=True)),
    ("serving_since", sa.DateTime(timezone=True)),
    ("serving_alerted_at", sa.DateTime(timezone=True)),
)


def _columns() -> set[str] | None:
    insp = sa.inspect(op.get_bind())
    if "domains" not in set(insp.get_table_names()):
        return None
    return {c["name"] for c in insp.get_columns("domains")}


def upgrade():
    have = _columns()
    if have is None:
        return
    for name, type_ in _COLUMNS:
        if name not in have:
            op.add_column("domains", sa.Column(name, type_, nullable=True))


def downgrade():
    have = _columns()
    if have is None:
        return
    for name, _type in reversed(_COLUMNS):
        if name in have:
            op.drop_column("domains", name)
