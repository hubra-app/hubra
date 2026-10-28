"""plugins: installed plugins, archives, repositories and keys

Public-schema tables only, so the revision is safe to run again per club
(flask migrate-tenants): every table goes to public, once.  Also drops the
inventory_items.guide and guide_url columns an earlier revision added,
when they hold nothing; the guides plugin moves them when they do.

Revision ID: 202ee240e1d8
Revises: 1894b9307388
Create Date: 2026-10-28 09:36:28.580856

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "202ee240e1d8"
down_revision = "1894b9307388"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_table(table, schema):
    return sa.inspect(op.get_bind()).has_table(table, schema=schema)


def upgrade():
    schema = _public_schema()
    if not _has_table("plugin_archives", schema):
        op.create_table(
            "plugin_archives",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plugin_id", sa.String(length=64), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("sha256", name="uq_plugin_archive_sha"),
            schema=schema,
        )
        op.create_index(
            "ix_plugin_archives_plugin_id",
            "plugin_archives",
            ["plugin_id"],
            schema=schema,
        )
    if not _has_table("plugin_repositories", schema):
        op.create_table(
            "plugin_repositories",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=False),
            sa.Column("key_id", sa.String(length=16), nullable=False),
            sa.Column("public_key", sa.Text(), nullable=False),
            sa.Column("official", sa.Boolean(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("added_by", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
            sa.UniqueConstraint("url"),
            schema=schema,
        )
    if not _has_table("plugin_state", schema):
        op.create_table(
            "plugin_state",
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("key"),
            schema=schema,
        )
    if not _has_table("plugin_trusted_keys", schema):
        op.create_table(
            "plugin_trusted_keys",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("key_id", sa.String(length=16), nullable=False),
            sa.Column("public_key", sa.Text(), nullable=False),
            sa.Column("added_by", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key_id"),
            sa.UniqueConstraint("name"),
            schema=schema,
        )
    if not _has_table("installed_plugins", schema):
        op.create_table(
            "installed_plugins",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=False),
            sa.Column("source", sa.String(length=16), nullable=False),
            sa.Column("origin", sa.String(length=500), nullable=False),
            sa.Column("repository_id", sa.Integer(), nullable=True),
            sa.Column("trust", sa.String(length=16), nullable=False),
            sa.Column("signer", sa.String(length=255), nullable=False),
            sa.Column("key_id", sa.String(length=16), nullable=False),
            sa.Column("archive_sha256", sa.String(length=64), nullable=True),
            sa.Column("previous_sha256", sa.String(length=64), nullable=True),
            sa.Column("held_version", sa.String(length=64), nullable=True),
            sa.Column("installed_by", sa.String(length=255), nullable=False),
            sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("error", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(
                ["repository_id"],
                [
                    f"{schema}.plugin_repositories.id"
                    if schema
                    else "plugin_repositories.id"
                ],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )

    # Guides moved to a plugin with its own table.  Empty columns go now;
    # columns with guides in them wait for the guides plugin to move them.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("inventory_items"):
        cols = {c["name"] for c in insp.get_columns("inventory_items")}
        if {"guide", "guide_url"} <= cols:
            used = bind.execute(
                sa.text(
                    "SELECT COUNT(*) FROM inventory_items "
                    "WHERE guide IS NOT NULL OR guide_url IS NOT NULL"
                )
            ).scalar()
            if not used:
                with op.batch_alter_table("inventory_items") as batch_op:
                    batch_op.drop_column("guide_url")
                    batch_op.drop_column("guide")


def downgrade():
    schema = _public_schema()
    op.drop_table("installed_plugins", schema=schema)
    op.drop_table("plugin_trusted_keys", schema=schema)
    op.drop_table("plugin_state", schema=schema)
    op.drop_table("plugin_repositories", schema=schema)
    op.drop_index("ix_plugin_archives_plugin_id", "plugin_archives", schema=schema)
    op.drop_table("plugin_archives", schema=schema)
