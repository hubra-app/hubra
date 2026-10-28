"""add feature_flag table

Revision ID: 8dd18599708d
Revises: 759b24d8c462
Create Date: 2026-07-08 09:57:46.810164

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8dd18599708d"
down_revision = "759b24d8c462"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feature_flag",
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # ── Data migration: move mail.enabled Setting → FeatureFlag ──────────
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT value FROM setting WHERE key = 'mail.enabled'")
    ).fetchone()

    mail_enabled = False
    if row is not None and row[0] is not None:
        mail_enabled = str(row[0]).strip().lower() == "true"

    conn.execute(
        sa.text(
            "INSERT INTO feature_flag (key, enabled, label, description) "
            "VALUES ('mail', :enabled, 'Mail', "
            "'Managed mail (WildDuck mailboxes, aliases, reconciliation, and sync)')"
        ),
        {"enabled": mail_enabled},
    )

    conn.execute(sa.text("DELETE FROM setting WHERE key = 'mail.enabled'"))


def downgrade():
    conn = op.get_bind()

    row = conn.execute(
        sa.text("SELECT enabled FROM feature_flag WHERE key = 'mail'")
    ).fetchone()

    mail_enabled_str = "false"
    if row is not None and row[0]:
        mail_enabled_str = "true"

    conn.execute(
        sa.text(
            "INSERT INTO setting (key, value, namespace, sensitive, required, restricted, is_default, default_value) "
            "VALUES ('mail.enabled', :val, 'general', 0, 0, 0, 1, 'false') "
            "ON CONFLICT (key) DO UPDATE SET value = :val"
        ),
        {"val": mail_enabled_str},
    )

    op.drop_table("feature_flag")
