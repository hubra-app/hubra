"""Role and Permission models — RBAC for Hubra."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class Permission(db.Model):
    """Master list of all permissions, auto-synced from route decorators.

    A Permission row is created by `flask sync-permissions` for every route
    decorated with @permission_required.  The ``key`` is a structured string
    ``{blueprint}.{resource}.{action}`` used in code; ``display_name`` is the
    human-readable label shown in the admin UI.
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    resource: Mapped[str] = mapped_column(db.String(100), nullable=False)
    action: Mapped[str] = mapped_column(db.String(100), nullable=False)
    blueprint: Mapped[str] = mapped_column(db.String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission_rel", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Permission id={self.id} key={self.key!r}>"


class Role(db.Model):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    # Seeded/default rows are protected from deletion
    is_default: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    # System roles are protected from deletion/renaming
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    # Marks the Owner system role (un-lockoutable, always >=1 per tenant)
    is_owner: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    description: Mapped[str | None] = mapped_column(db.Text, nullable=True)

    # Relationships
    members: Mapped[list["Member"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", secondary="member_roles", back_populates="roles"
    )
    permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name!r}>"


class RolePermission(db.Model):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id"),
        UniqueConstraint("role_id", "permission"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Legacy free-text permission string — kept for backward compatibility
    # during the RBAC migration. Will be removed after all routes are migrated.
    permission: Mapped[str | None] = mapped_column(db.String(100), nullable=True)

    role: Mapped["Role"] = relationship("Role", back_populates="permissions")
    permission_rel: Mapped["Permission | None"] = relationship(
        "Permission", back_populates="role_permissions"
    )

    def __repr__(self) -> str:
        return f"<RolePermission role_id={self.role_id} permission_id={self.permission_id}>"
