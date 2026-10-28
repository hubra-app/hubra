"""migrate identity attributes from member to user

Revision ID: 28a0702d778a
Revises: adbd522485c5
Create Date: 2026-07-13 07:58:06.625331

Migrates all personal identity attributes from the per-tenant Member table
to the global User table. Member becomes a thin link table.

The migration is structured in phases:
1. Add new columns to users (nullable)
2. Copy data from members → users (create Users for members without user_id)
3. Migrate password_reset_tokens and email_verification_tokens FKs
4. Drop identity columns from members (public + all tenant schemas)
5. Drop legacy name column from users, set NOT NULL on new columns
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "28a0702d778a"
down_revision = "adbd522485c5"
branch_labels = None
depends_on = None

# Columns to copy from members to users
_IDENTITY_COLUMNS = [
    "first_name",
    "last_name",
    "password_hash",
    "avatar",
    "avatar_color",
    "must_change_password",
    "is_disabled",
    "failed_login_count",
    "locked_until",
    "last_seen",
    "private_email_verified",
    "language",
    "phone",
    "mobile",
    "birthday",
    "address_street",
    "address_house_no",
    "address_postal_code",
    "address_city",
    "address_country",
    "emergency_contact",
    "profile_note",
]

# Columns to drop from members
_DROP_COLUMNS = _IDENTITY_COLUMNS + ["last_login_ip", "last_login_ua", "email"]


def upgrade():
    bind = op.get_bind()

    # ── Phase 1: Add new columns to users (nullable) ────────────────────────
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("first_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("avatar_color", sa.String(length=7), nullable=True)
        )
        batch_op.add_column(sa.Column("is_disabled", sa.Boolean(), nullable=True))
        batch_op.add_column(
            sa.Column("must_change_password", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("failed_login_count", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("private_email_verified", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(sa.Column("language", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("phone", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("mobile", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("birthday", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("address_street", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_house_no", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_postal_code", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_city", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_country", sa.String(length=2), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "emergency_contact",
                postgresql.JSONB(astext_type=sa.Text()).with_variant(
                    sa.JSON(), "sqlite"
                ),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("profile_note", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
        )

    # Drop name column early — it's NOT NULL and blocks INSERTs of new Users
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("name")

    # ── Phase 2: Copy data from members to users ────────────────────────────
    if bind.dialect.name == "postgresql":
        _migrate_data_postgresql(bind)
    else:
        _migrate_data_sqlite(bind)

    # ── Phase 3: Set NOT NULL and defaults on users columns ─────────────────
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("first_name", nullable=False)
        batch_op.alter_column("last_name", nullable=False)
        batch_op.alter_column("avatar_color", nullable=False, server_default="#6366f1")
        batch_op.alter_column(
            "is_disabled", nullable=False, server_default=sa.text("false")
        )
        batch_op.alter_column(
            "must_change_password", nullable=False, server_default=sa.text("false")
        )
        batch_op.alter_column(
            "failed_login_count", nullable=False, server_default=sa.text("0")
        )
        batch_op.alter_column(
            "private_email_verified", nullable=False, server_default=sa.text("false")
        )
        batch_op.alter_column("language", nullable=False, server_default="de-CH")
        batch_op.alter_column("address_country", nullable=False, server_default="CH")
        batch_op.alter_column(
            "updated_at", nullable=False, server_default=sa.text("now()")
        )

    # ── Phase 4: Migrate password_reset_tokens FK ───────────────────────────
    with op.batch_alter_table("password_reset_tokens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
    # Copy member_id → user_id via member.user_id
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "UPDATE password_reset_tokens SET user_id = m.user_id "
                "FROM members m WHERE password_reset_tokens.member_id = m.id "
                "AND m.user_id IS NOT NULL"
            )
        )
    else:
        bind.execute(
            sa.text(
                "UPDATE password_reset_tokens SET user_id = "
                "(SELECT m.user_id FROM members m WHERE m.id = password_reset_tokens.member_id "
                "AND m.user_id IS NOT NULL)"
            )
        )
    # Set remaining to 0 or find user by email — for safety, delete orphaned tokens
    bind.execute(sa.text("DELETE FROM password_reset_tokens WHERE user_id IS NULL"))
    with op.batch_alter_table("password_reset_tokens", schema=None) as batch_op:
        batch_op.alter_column("user_id", nullable=False)
        batch_op.drop_constraint(
            batch_op.f("password_reset_tokens_member_id_fkey"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "password_reset_tokens_user_id_fkey",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_column("member_id")

    # ── Phase 5: Migrate email_verification_tokens FK ───────────────────────
    with op.batch_alter_table("email_verification_tokens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "UPDATE email_verification_tokens SET user_id = m.user_id "
                "FROM members m WHERE email_verification_tokens.member_id = m.id "
                "AND m.user_id IS NOT NULL"
            )
        )
    else:
        bind.execute(
            sa.text(
                "UPDATE email_verification_tokens SET user_id = "
                "(SELECT m.user_id FROM members m WHERE m.id = email_verification_tokens.member_id "
                "AND m.user_id IS NOT NULL)"
            )
        )
    bind.execute(sa.text("DELETE FROM email_verification_tokens WHERE user_id IS NULL"))
    with op.batch_alter_table("email_verification_tokens", schema=None) as batch_op:
        batch_op.alter_column("user_id", nullable=False)
        batch_op.drop_constraint(
            batch_op.f("email_verification_tokens_member_id_fkey"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "email_verification_tokens_user_id_fkey",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_column("member_id")

    # ── Phase 6: Drop identity columns from members (public schema) ─────────
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("members_email_key"), type_="unique")
        for col in _DROP_COLUMNS:
            batch_op.drop_column(col)

    # ── Phase 7: Drop identity columns from all tenant schemas ──────────────
    if bind.dialect.name == "postgresql":
        _drop_columns_from_tenant_schemas(bind)


def _migrate_data_postgresql(bind):
    """Copy identity data from members to users on PostgreSQL.

    Iterates all schemas (public + tenant_{id}.*) and copies member
    identity fields to the corresponding users row. For members without
    a user_id, creates a new User and links the member.
    """
    # Get all tenant schemas
    tenant_ids = bind.execute(
        sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL")
    ).fetchall()

    schemas = ["public"] + [f"tenant_{t[0]}" for t in tenant_ids]

    for schema in schemas:
        # Set search_path to the schema so member queries resolve
        bind.execute(sa.text(f"SET search_path TO {schema}, public"))

        # Get all members with their identity data
        members = bind.execute(
            sa.text(
                "SELECT id, user_id, first_name, last_name, email, password_hash, "
                "avatar, avatar_color, must_change_password, is_disabled, "
                "failed_login_count, locked_until, last_seen, private_email_verified, "
                "language, phone, mobile, birthday, address_street, address_house_no, "
                "address_postal_code, address_city, address_country, "
                "emergency_contact, profile_note "
                f"FROM {schema}.members"
            )
        ).fetchall()

        for m in members:
            (
                mid,
                uid,
                first_name,
                last_name,
                email,
                pwd,
                avatar,
                avatar_color,
                mcp,
                disabled,
                flc,
                locked,
                last_seen,
                pev,
                lang,
                phone,
                mobile,
                birthday,
                addr_street,
                addr_hno,
                addr_pcode,
                addr_city,
                addr_country,
                emerg,
                profile_note,
            ) = m

            if uid is not None:
                # Update existing User with identity data (only if not already set)
                bind.execute(
                    sa.text(
                        "UPDATE users SET "
                        "first_name = COALESCE(first_name, :first_name), "
                        "last_name = COALESCE(last_name, :last_name), "
                        "password_hash = COALESCE(NULLIF(password_hash, ''), :pwd), "
                        "avatar = COALESCE(avatar, :avatar), "
                        "avatar_color = COALESCE(NULLIF(avatar_color, ''), :avatar_color), "
                        "must_change_password = COALESCE(must_change_password, :mcp), "
                        "is_disabled = COALESCE(is_disabled, :disabled), "
                        "failed_login_count = COALESCE(failed_login_count, :flc), "
                        "locked_until = COALESCE(locked_until, :locked), "
                        "last_seen = COALESCE(last_seen, :last_seen), "
                        "private_email_verified = COALESCE(private_email_verified, :pev), "
                        "language = COALESCE(NULLIF(language, ''), :lang), "
                        "phone = COALESCE(phone, :phone), "
                        "mobile = COALESCE(mobile, :mobile), "
                        "birthday = COALESCE(birthday, :birthday), "
                        "address_street = COALESCE(address_street, :addr_street), "
                        "address_house_no = COALESCE(address_house_no, :addr_hno), "
                        "address_postal_code = COALESCE(address_postal_code, :addr_pcode), "
                        "address_city = COALESCE(address_city, :addr_city), "
                        "address_country = COALESCE(NULLIF(address_country, ''), :addr_country), "
                        "emergency_contact = COALESCE(emergency_contact, :emerg), "
                        "profile_note = COALESCE(profile_note, :profile_note) "
                        "WHERE id = :uid"
                    ),
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "pwd": pwd,
                        "avatar": avatar,
                        "avatar_color": avatar_color or "#6366f1",
                        "mcp": mcp,
                        "disabled": disabled,
                        "flc": flc,
                        "locked": locked,
                        "last_seen": last_seen,
                        "pev": pev,
                        "lang": lang or "de-CH",
                        "phone": phone,
                        "mobile": mobile,
                        "birthday": birthday,
                        "addr_street": addr_street,
                        "addr_hno": addr_hno,
                        "addr_pcode": addr_pcode,
                        "addr_city": addr_city,
                        "addr_country": addr_country or "CH",
                        "emerg": emerg,
                        "profile_note": profile_note,
                        "uid": uid,
                    },
                )
            else:
                # Check if a User with this email already exists
                existing = bind.execute(
                    sa.text("SELECT id FROM users WHERE email = :email"),
                    {"email": email},
                ).fetchone()

                if existing:
                    new_uid = existing[0]
                    # Update with member data
                    bind.execute(
                        sa.text(
                            "UPDATE users SET "
                            "first_name = COALESCE(first_name, :first_name), "
                            "last_name = COALESCE(last_name, :last_name), "
                            "password_hash = COALESCE(NULLIF(password_hash, ''), :pwd) "
                            "WHERE id = :uid"
                        ),
                        {
                            "first_name": first_name,
                            "last_name": last_name,
                            "pwd": pwd,
                            "uid": new_uid,
                        },
                    )
                else:
                    # Create new User from member data
                    # Split name if first_name/last_name not available
                    fn = first_name or email.split("@")[0]
                    ln = last_name or ""
                    result = bind.execute(
                        sa.text(
                            "INSERT INTO users (email, password_hash, first_name, last_name, "
                            "avatar, avatar_color, is_superadmin, is_disabled, "
                            "must_change_password, failed_login_count, locked_until, "
                            "last_seen, private_email_verified, language, phone, mobile, "
                            "birthday, address_street, address_house_no, address_postal_code, "
                            "address_city, address_country, emergency_contact, profile_note, "
                            "created_at, updated_at) "
                            "VALUES (:email, :pwd, :fn, :ln, :avatar, :ac, false, :disabled, "
                            ":mcp, :flc, :locked, :last_seen, :pev, :lang, :phone, :mobile, "
                            ":birthday, :addr_s, :addr_h, :addr_p, :addr_c, :addr_co, "
                            ":emerg, :pn, now(), now()) RETURNING id"
                        ),
                        {
                            "email": email,
                            "pwd": pwd,
                            "fn": fn,
                            "ln": ln,
                            "avatar": avatar,
                            "ac": avatar_color or "#6366f1",
                            "disabled": disabled or False,
                            "mcp": mcp or False,
                            "flc": flc or 0,
                            "locked": locked,
                            "last_seen": last_seen,
                            "pev": pev or False,
                            "lang": lang or "de-CH",
                            "phone": phone,
                            "mobile": mobile,
                            "birthday": birthday,
                            "addr_s": addr_street,
                            "addr_h": addr_hno,
                            "addr_p": addr_pcode,
                            "addr_c": addr_city,
                            "addr_co": addr_country or "CH",
                            "emerg": emerg,
                            "pn": profile_note,
                        },
                    )
                    new_uid = result.fetchone()[0]

                # Link member to user
                bind.execute(
                    sa.text(
                        f"UPDATE {schema}.members SET user_id = :uid WHERE id = :mid"
                    ),
                    {"uid": new_uid, "mid": mid},
                )

        # Also create UserTenant links if not already present
        if schema != "public":
            tenant_id = int(schema.replace("tenant_", ""))
            bind.execute(
                sa.text(
                    f"INSERT INTO user_tenants (user_id, tenant_id) "
                    f"SELECT DISTINCT m.user_id, :tid FROM {schema}.members m "
                    f"WHERE m.user_id IS NOT NULL "
                    f"AND NOT EXISTS ("
                    f"  SELECT 1 FROM user_tenants ut "
                    f"  WHERE ut.user_id = m.user_id AND ut.tenant_id = :tid)"
                ),
                {"tid": tenant_id},
            )

        bind.execute(sa.text("SET search_path TO public"))


def _migrate_data_sqlite(bind):
    """Copy identity data from members to users on SQLite (tests)."""
    members = bind.execute(
        sa.text(
            "SELECT id, user_id, first_name, last_name, email, password_hash, "
            "avatar, avatar_color, must_change_password, is_disabled, "
            "failed_login_count, locked_until, last_seen, private_email_verified, "
            "language, phone, mobile, birthday, address_street, address_house_no, "
            "address_postal_code, address_city, address_country, "
            "emergency_contact, profile_note FROM members"
        )
    ).fetchall()

    for m in members:
        (
            mid,
            uid,
            first_name,
            last_name,
            email,
            pwd,
            avatar,
            avatar_color,
            mcp,
            disabled,
            flc,
            locked,
            last_seen,
            pev,
            lang,
            phone,
            mobile,
            birthday,
            addr_street,
            addr_hno,
            addr_pcode,
            addr_city,
            addr_country,
            emerg,
            profile_note,
        ) = m

        if uid is not None:
            bind.execute(
                sa.text(
                    "UPDATE users SET "
                    "first_name = COALESCE(first_name, :first_name), "
                    "last_name = COALESCE(last_name, :last_name), "
                    "password_hash = COALESCE(NULLIF(password_hash, ''), :pwd), "
                    "avatar = COALESCE(avatar, :avatar), "
                    "avatar_color = COALESCE(NULLIF(avatar_color, ''), :avatar_color), "
                    "must_change_password = COALESCE(must_change_password, :mcp), "
                    "is_disabled = COALESCE(is_disabled, :disabled), "
                    "failed_login_count = COALESCE(failed_login_count, :flc), "
                    "private_email_verified = COALESCE(private_email_verified, :pev), "
                    "language = COALESCE(NULLIF(language, ''), :lang), "
                    "phone = COALESCE(phone, :phone), "
                    "mobile = COALESCE(mobile, :mobile) "
                    "WHERE id = :uid"
                ),
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "pwd": pwd,
                    "avatar": avatar,
                    "avatar_color": avatar_color or "#6366f1",
                    "mcp": mcp,
                    "disabled": disabled,
                    "flc": flc,
                    "pev": pev,
                    "lang": lang or "de-CH",
                    "phone": phone,
                    "mobile": mobile,
                    "uid": uid,
                },
            )
        else:
            existing = bind.execute(
                sa.text("SELECT id FROM users WHERE email = :email"), {"email": email}
            ).fetchone()

            if existing:
                new_uid = existing[0]
            else:
                fn = first_name or email.split("@")[0]
                ln = last_name or ""
                result = bind.execute(
                    sa.text(
                        "INSERT INTO users (email, password_hash, first_name, last_name, "
                        "avatar, avatar_color, is_superadmin, is_disabled, "
                        "must_change_password, failed_login_count, private_email_verified, "
                        "language, phone, mobile, created_at, updated_at) "
                        "VALUES (:email, :pwd, :fn, :ln, :avatar, :ac, 0, :disabled, "
                        ":mcp, :flc, :pev, :lang, :phone, :mobile, "
                        "datetime('now'), datetime('now'))"
                    ),
                    {
                        "email": email,
                        "pwd": pwd,
                        "fn": fn,
                        "ln": ln,
                        "avatar": avatar,
                        "ac": avatar_color or "#6366f1",
                        "disabled": 0 if not disabled else 1,
                        "mcp": 0 if not mcp else 1,
                        "flc": flc or 0,
                        "pev": 0 if not pev else 1,
                        "lang": lang or "de-CH",
                        "phone": phone,
                        "mobile": mobile,
                    },
                )
                new_uid = result.lastrowid

            bind.execute(
                sa.text("UPDATE members SET user_id = :uid WHERE id = :mid"),
                {"uid": new_uid, "mid": mid},
            )


def _drop_columns_from_tenant_schemas(bind):
    """Drop identity columns from all tenant_{id} schemas on PostgreSQL."""
    tenant_ids = bind.execute(
        sa.text("SELECT id FROM tenants WHERE deleted_at IS NULL")
    ).fetchall()

    for (tenant_id,) in tenant_ids:
        schema = f"tenant_{tenant_id}"
        for col in _DROP_COLUMNS:
            bind.execute(
                sa.text(f"ALTER TABLE {schema}.members DROP COLUMN IF EXISTS {col}")
            )


def downgrade():
    # This migration is not easily reversible due to the data migration.
    # A full downgrade would require copying data back from users to members.
    # For safety, we only restore the schema shape without data.
    with op.batch_alter_table("email_verification_tokens", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("member_id", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.drop_constraint(
            "email_verification_tokens_user_id_fkey", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("email_verification_tokens_member_id_fkey"),
            "members",
            ["member_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_column("user_id")

    with op.batch_alter_table("password_reset_tokens", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("member_id", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.drop_constraint(
            "password_reset_tokens_user_id_fkey", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("password_reset_tokens_member_id_fkey"),
            "members",
            ["member_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_column("user_id")

    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("first_name", sa.String(255), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("last_name", sa.String(255), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("email", sa.String(255), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("password_hash", sa.Text, nullable=False, server_default="")
        )
        batch_op.create_unique_constraint(batch_op.f("members_email_key"), ["email"])

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("name", sa.String(255), nullable=False, server_default="")
        )
        batch_op.drop_column("updated_at")
        batch_op.drop_column("profile_note")
        batch_op.drop_column("emergency_contact")
        batch_op.drop_column("address_country")
        batch_op.drop_column("address_city")
        batch_op.drop_column("address_postal_code")
        batch_op.drop_column("address_house_no")
        batch_op.drop_column("address_street")
        batch_op.drop_column("birthday")
        batch_op.drop_column("mobile")
        batch_op.drop_column("phone")
        batch_op.drop_column("language")
        batch_op.drop_column("private_email_verified")
        batch_op.drop_column("last_seen")
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_login_count")
        batch_op.drop_column("must_change_password")
        batch_op.drop_column("is_disabled")
        batch_op.drop_column("avatar_color")
        batch_op.drop_column("last_name")
        batch_op.drop_column("first_name")
