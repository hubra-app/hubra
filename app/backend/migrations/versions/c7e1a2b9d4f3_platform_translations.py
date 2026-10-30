"""Translations belong to the platform; clubs suggest changes

Every club schema had its own ``translation`` table over the platform's.
Clubs now read the platform's texts (public.translation) and suggest
changes in ``translation_requests``, which a platform admin accepts or
rejects. A club's own texts that differ from the platform's become pending
suggestions, so no wording is lost; then the club tables are dropped.

Revision ID: c7e1a2b9d4f3
Revises: a9c4e2f7d1b6
Create Date: 2026-10-30 16:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c7e1a2b9d4f3"
down_revision = "a9c4e2f7d1b6"
branch_labels = None
depends_on = None

_NOTE = "Aus der bisherigen Vereinsübersetzung übernommen"


def _canonical(code: str) -> str:
    parts = code.replace("_", "-").split("-")
    out = [parts[0].lower()]
    for part in parts[1:]:
        out.append(part.upper() if len(part) == 2 else part.title() if len(part) == 4 else part.lower())
    return "-".join(out)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "translation_requests" not in inspector.get_table_names():
        op.create_table(
            "translation_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("locale", sa.String(10), nullable=False),
            sa.Column("key", sa.String(255), nullable=False),
            sa.Column("current_value", sa.Text(), nullable=True),
            sa.Column("proposed_value", sa.Text(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("decision_note", sa.Text(), nullable=True),
            sa.Column(
                "decided_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_translation_requests_tenant_id", "translation_requests", ["tenant_id"])
        op.create_index("ix_translation_requests_status", "translation_requests", ["status"])

    if bind.dialect.name != "postgresql":
        return

    platform = {
        (row.locale, row.key): row.value
        for row in bind.execute(sa.text("SELECT locale, key, value FROM public.translation"))
    }
    schemas = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'translation' AND table_schema LIKE 'tenant\\_%'"
        )
    ).scalars().all()
    for schema in schemas:
        try:
            tenant_id = int(schema.removeprefix("tenant_"))
        except ValueError:
            continue
        exists = bind.execute(
            sa.text("SELECT 1 FROM public.tenants WHERE id = :id"), {"id": tenant_id}
        ).first()
        if exists:
            rows = bind.execute(
                sa.text(
                    f'SELECT locale, key, value FROM "{schema}".translation '
                    "WHERE alias_for IS NULL AND value <> ''"
                )
            ).all()
            for row in rows:
                locale = _canonical(row.locale)
                value = row.value.strip()
                current = platform.get((locale, row.key))
                if not value or value == row.key or value == current:
                    continue
                bind.execute(
                    sa.text(
                        "INSERT INTO public.translation_requests "
                        "(tenant_id, locale, key, current_value, proposed_value, note, status) "
                        "VALUES (:t, :l, :k, :c, :v, :n, 'pending')"
                    ),
                    {"t": tenant_id, "l": locale, "k": row.key, "c": current, "v": value, "n": _NOTE},
                )
        op.execute(f'DROP TABLE "{schema}".translation')


def downgrade():
    # The club tables come back empty; clubs read the platform texts either way.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        schemas = bind.execute(
            sa.text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant\\_%'"
            )
        ).scalars().all()
        for schema in schemas:
            op.execute(
                f'CREATE TABLE IF NOT EXISTS "{schema}".translation '
                "(LIKE public.translation INCLUDING ALL)"
            )
    op.drop_index("ix_translation_requests_status", table_name="translation_requests")
    op.drop_index("ix_translation_requests_tenant_id", table_name="translation_requests")
    op.drop_table("translation_requests")
