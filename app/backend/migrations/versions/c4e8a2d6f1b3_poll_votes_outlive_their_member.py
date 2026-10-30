"""Poll votes stay, anonymous, when their member is deleted

A permanent member delete removed the member's poll votes (member_id was
NOT NULL), so the totals of polls already decided changed afterwards.
member_id is nullable now and set to NULL on delete, in the template table
and in every club schema.

Revision ID: c4e8a2d6f1b3
Revises: b7e2d4f6a8c1
Create Date: 2026-10-29 07:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4e8a2d6f1b3"
down_revision = "b7e2d4f6a8c1"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    return list(
        bind.execute(
            sa.text(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = 'poll_votes' ORDER BY table_schema"
            )
        ).scalars()
    )


def _member_fks(schema):
    """Foreign keys of poll_votes.member_id (public has them; clubs do not)."""
    inspector = sa.inspect(op.get_bind())
    return [
        fk["name"]
        for fk in inspector.get_foreign_keys("poll_votes", schema=schema)
        if fk["constrained_columns"] == ["member_id"] and fk.get("name")
    ]


def _set_ondelete(schema, ondelete):
    for name in _member_fks(schema):
        op.drop_constraint(name, "poll_votes", schema=schema, type_="foreignkey")
        op.create_foreign_key(
            name,
            "poll_votes",
            "members",
            ["member_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
            ondelete=ondelete,
        )


def upgrade():
    for schema in _schemas():
        with op.batch_alter_table("poll_votes", schema=schema) as batch:
            batch.alter_column("member_id", existing_type=sa.Integer(), nullable=True)
        if op.get_bind().dialect.name == "postgresql":
            _set_ondelete(schema, "SET NULL")


def downgrade():
    # Anonymous votes cannot go back under NOT NULL: they are dropped.
    for schema in _schemas():
        table = f"{schema}.poll_votes" if schema else "poll_votes"
        op.execute(f"DELETE FROM {table} WHERE member_id IS NULL")
        with op.batch_alter_table("poll_votes", schema=schema) as batch:
            batch.alter_column("member_id", existing_type=sa.Integer(), nullable=False)
        if op.get_bind().dialect.name == "postgresql":
            _set_ondelete(schema, None)
