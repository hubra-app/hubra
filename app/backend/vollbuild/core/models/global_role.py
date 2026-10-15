"""Global RBAC models — platform-level roles and permissions.

These live in the public schema (alongside User, Tenant) and control
access to the manager portal (manage.vollbuild.ch). They are separate
from the tenant-scoped Role/Permission/RolePermission models which
control access within a single tenant's data.

The is_superadmin boolean on User remains as a bypass — superadmins
pass all permission checks regardless of their global role assignments.
"""

from __future__ import annotations

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db


class GlobalPermission(db.Model):
    """Master list of platform-level permissions.

    Keys are structured strings like ``tenants.read``, ``requests.approve``,
    ``audit.read``. Seeded at startup; can be extended via the management API.
    """

    __tablename__ = "global_permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text, nullable=True)

    role_permissions: Mapped[list["GlobalRolePermission"]] = relationship(
        "GlobalRolePermission",
        back_populates="permission_rel",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<GlobalPermission id={self.id} key={self.key!r}>"


class GlobalRole(db.Model):
    """Platform-level role (e.g. Superadmin, Manager, Support, Requester).

    System roles (is_system=True) are seeded at startup and protected from
    deletion. Custom roles can be created via the management API.
    """

    __tablename__ = "global_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)

    permissions: Mapped[list["GlobalRolePermission"]] = relationship(
        "GlobalRolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    user_assignments: Mapped[list["UserGlobalRole"]] = relationship(
        "UserGlobalRole",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<GlobalRole id={self.id} name={self.name!r}>"


class GlobalRolePermission(db.Model):
    """Join table: GlobalRole <-> GlobalPermission."""

    __tablename__ = "global_role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(
        db.ForeignKey("global_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[int] = mapped_column(
        db.ForeignKey("global_permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped["GlobalRole"] = relationship(
        "GlobalRole", back_populates="permissions"
    )
    permission_rel: Mapped["GlobalPermission"] = relationship(
        "GlobalPermission", back_populates="role_permissions"
    )

    def __repr__(self) -> str:
        return f"<GlobalRolePermission role_id={self.role_id} permission_id={self.permission_id}>"


class UserGlobalRole(db.Model):
    """Join table: User <-> GlobalRole.

    A user can have multiple global roles; their effective permission set
    is the union of permissions across all assigned roles.
    """

    __tablename__ = "user_global_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        db.ForeignKey("global_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped["GlobalRole"] = relationship(
        "GlobalRole", back_populates="user_assignments"
    )

    def __repr__(self) -> str:
        return f"<UserGlobalRole user_id={self.user_id} role_id={self.role_id}>"
