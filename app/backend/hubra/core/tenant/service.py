"""Tenant lifecycle service — provision, suspend, archive, delete, update."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select, text

from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant, GlobalAuditEntry

from .schema_manager import (
    create_tenant_schema,
    drop_tenant_schema,
)

_log = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")

_VALID_SORT_FIELDS = {"created_at", "name", "slug", "plan", "status", "updated_at"}


class TenantProvisioningError(Exception):
    """Raised when tenant provisioning fails (idempotent-safe)."""


class TenantService:
    """Service-layer for tenant lifecycle operations."""

    # ── Create ─────────────────────────────────────────────────────────────

    @staticmethod
    def provision_tenant(
        name: str,
        slug: str,
        plan: str = "starter",
        admin_email: str | None = None,
        admin_password: str | None = None,
        admin_user_id: int | None = None,
    ) -> Tenant:
        """Provision a new tenant end-to-end.

        Steps:
          1. Validate slug format and uniqueness.
          2. Create Tenant record in the public schema.
          3. Create the ``tenant_{id}`` PostgreSQL schema and clone tables.
          4. Seed default data (admin member, roles, settings).
          5. Return the created Tenant.

        Raises ``TenantProvisioningError`` on any failure; the transaction
        is rolled back so no partial state persists.
        """
        _validate_slug(slug)

        existing = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
        if existing:
            raise TenantProvisioningError(
                f"Tenant with slug '{slug}' already exists (id={existing.id})"
            )

        tenant = Tenant(name=name, slug=slug, plan=plan)
        db.session.add(tenant)
        db.session.flush()  # obtain tenant.id

        try:
            create_tenant_schema(tenant.id)
        except Exception as exc:
            db.session.rollback()
            raise TenantProvisioningError(
                f"Failed to create schema for tenant '{slug}': {exc}"
            ) from exc

        try:
            _seed_tenant(tenant.id, admin_email, admin_password, admin_user_id)
        except Exception as exc:
            _log.exception("Seed data failed for tenant %s, rolling back", slug)
            drop_tenant_schema(tenant.id)
            db.session.rollback()
            raise TenantProvisioningError(
                f"Failed to seed tenant '{slug}': {exc}"
            ) from exc

        db.session.add(
            GlobalAuditEntry(
                tenant_id=tenant.id,
                action="tenant.provision",
                target_type="Tenant",
                target_id=str(tenant.id),
                details={"name": name, "slug": slug, "plan": plan},
            )
        )
        db.session.commit()
        _log.info("Tenant '%s' (id=%d) provisioned successfully", slug, tenant.id)
        return tenant

    # ── Status transitions ─────────────────────────────────────────────────

    @staticmethod
    def set_status(tenant_id: int, status: str) -> Tenant | None:
        """Transition a tenant to *status* (active / suspended / archived)."""
        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None:
            return None
        old_status = tenant.status
        tenant.status = status
        db.session.add(
            GlobalAuditEntry(
                tenant_id=tenant_id,
                action=f"tenant.{status}",
                target_type="Tenant",
                target_id=str(tenant_id),
                details={"old_status": old_status, "new_status": status},
            )
        )
        db.session.commit()
        _log.info("Tenant %d status → %s", tenant_id, status)
        return tenant

    @staticmethod
    def suspend(tenant_id: int) -> Tenant | None:
        return TenantService.set_status(tenant_id, "suspended")

    @staticmethod
    def archive(tenant_id: int) -> Tenant | None:
        return TenantService.set_status(tenant_id, "archived")

    @staticmethod
    def activate(tenant_id: int) -> Tenant | None:
        return TenantService.set_status(tenant_id, "active")

    # ── Update ─────────────────────────────────────────────────────────────

    @staticmethod
    def update_tenant(
        tenant_id: int,
        *,
        name: str | None = None,
        plan: str | None = None,
        settings: dict | None = None,
    ) -> Tenant | None:
        """Update general tenant attributes (name, plan, settings).

        Only provided keyword args are applied — omitting a field leaves it
        unchanged.  ``settings`` is merged into the existing JSONB dict.
        """
        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None:
            return None

        changes: dict[str, Any] = {}
        if name is not None and name != tenant.name:
            tenant.name = name
            changes["name"] = name
        if plan is not None and plan != tenant.plan:
            tenant.plan = plan
            changes["plan"] = plan
        if settings is not None:
            current = dict(tenant.settings or {})
            current.update(settings)
            tenant.settings = current
            changes["settings"] = settings

        if changes:
            db.session.add(
                GlobalAuditEntry(
                    tenant_id=tenant_id,
                    action="tenant.update",
                    target_type="Tenant",
                    target_id=str(tenant_id),
                    details=changes,
                )
            )
            db.session.commit()
            _log.info("Tenant %d updated: %s", tenant_id, list(changes))

        return tenant

    # ── Delete ─────────────────────────────────────────────────────────────

    @staticmethod
    def soft_delete(tenant_id: int) -> Tenant | None:
        """Soft-delete a tenant: set ``deleted_at`` and mark status as 'archived'.

        The record and schema are preserved.  The tenant is excluded from
        default query results via ``list_tenants(include_deleted=False)``.
        """
        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None:
            return None

        now = datetime.now(timezone.utc)
        old_status = tenant.status
        tenant.deleted_at = now
        tenant.status = "archived"
        db.session.add(
            GlobalAuditEntry(
                tenant_id=tenant_id,
                action="tenant.soft_delete",
                target_type="Tenant",
                target_id=str(tenant_id),
                details={"slug": tenant.slug, "old_status": old_status},
            )
        )
        db.session.commit()
        _log.info("Tenant %d soft-deleted (slug=%s)", tenant_id, tenant.slug)
        return tenant

    @staticmethod
    def delete_tenant(tenant_id: int, *, force: bool = False) -> bool:
        """Delete a tenant.

        By default performs a **soft-delete** (sets ``deleted_at``, preserves
        data).  When ``force=True``, drops the schema and removes the record
        permanently.
        """
        if not force:
            return TenantService.soft_delete(tenant_id) is not None

        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None:
            return False

        slug = tenant.slug
        db.session.add(
            GlobalAuditEntry(
                tenant_id=tenant_id,
                action="tenant.delete",
                target_type="Tenant",
                target_id=str(tenant_id),
                details={"slug": slug},
            )
        )
        drop_tenant_schema(tenant_id)
        db.session.execute(delete(Tenant).where(Tenant.id == tenant_id))
        db.session.commit()
        _log.warning("Tenant '%s' (id=%d) deleted permanently", slug, tenant_id)
        return True

    # ── Query helpers ──────────────────────────────────────────────────────

    @staticmethod
    def list_tenants(
        *,
        search: str | None = None,
        plan: str | None = None,
        status: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "asc",
        page: int = 1,
        per_page: int = 20,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        """List tenants with optional search, filtering, sorting, and pagination.

        Returns ``{"tenants": [...], "total": int, "page": int, "per_page": int}``.
        """
        query = select(Tenant)

        if not include_deleted:
            query = query.where(Tenant.deleted_at.is_(None))

        if search:
            pattern = f"%{search}%"
            query = query.where(
                (Tenant.name.ilike(pattern)) | (Tenant.slug.ilike(pattern))
            )

        if plan:
            query = query.where(Tenant.plan == plan)

        if status:
            query = query.where(Tenant.status == status)

        sort_field = sort_by if sort_by in _VALID_SORT_FIELDS else "created_at"
        sort_col = getattr(Tenant, sort_field)
        if sort_dir.lower() == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        # Count total matching rows (before pagination)
        count_query = select(db.func.count()).select_from(query.subquery())
        total = db.session.scalar(count_query) or 0

        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        tenants = list(db.session.scalars(query).all())
        return {
            "tenants": tenants,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    @staticmethod
    def get_by_slug(slug: str) -> Tenant | None:
        return db.session.scalar(select(Tenant).where(Tenant.slug == slug))

    @staticmethod
    def get_by_id(tenant_id: int) -> Tenant | None:
        return db.session.get(Tenant, tenant_id)

    @staticmethod
    def get_usage_stats(tenant_id: int) -> dict[str, Any]:
        """Return usage statistics for a tenant.

        Returns member count, domain count, and basic provisioning info.
        Storage metrics are a sum of mail quota + DB + backup sizes.
        API call counts are read from Redis counters (api.metrics middleware).
        """
        from hubra.core.models.domain import Domain
        from hubra.core.models.user_tenant import UserTenant

        tenant = db.session.get(Tenant, tenant_id)
        if tenant is None:
            return {}

        member_count = 0
        try:
            from .context import set_search_path

            set_search_path(tenant_id)
            from hubra.core.models.member import Member

            member_count = (
                db.session.scalar(
                    select(db.func.count())
                    .select_from(Member)
                    .where(Member.archived_at.is_(None))
                )
                or 0
            )
        except Exception:
            _log.debug("Could not count members for tenant %d", tenant_id)
        finally:
            try:
                db.session.execute(text("SET search_path TO public"))
            except Exception:
                pass

        domain_count = (
            db.session.scalar(
                select(db.func.count())
                .select_from(Domain)
                .where(Domain.tenant_id == tenant_id)
            )
            or 0
        )

        user_count = (
            db.session.scalar(
                select(db.func.count())
                .select_from(UserTenant)
                .where(UserTenant.tenant_id == tenant_id)
            )
            or 0
        )

        audit_count = (
            db.session.scalar(
                select(db.func.count())
                .select_from(GlobalAuditEntry)
                .where(GlobalAuditEntry.tenant_id == tenant_id)
            )
            or 0
        )

        return {
            "tenant_id": tenant_id,
            "member_count": member_count,
            "domain_count": domain_count,
            "user_count": user_count,
            "audit_entry_count": audit_count,
            "storage_bytes": _get_storage_bytes(tenant_id),
            "api_calls_30d": _get_api_calls_30d(tenant_id),
            "plan": tenant.plan,
            "status": tenant.status,
        }


# ── Internal helpers ───────────────────────────────────────────────────────


def _get_api_calls_30d(tenant_id: int) -> int:
    """Return API call count for the tenant in the last 30 days.

    Reads from Redis counters maintained by the api.metrics middleware.
    Returns 0 silently on any error (monitoring must never block usage stats).
    """
    try:
        from hubra.api.metrics import get_api_calls_30d

        return get_api_calls_30d(tenant_id)
    except Exception:
        return 0


def _get_storage_bytes(tenant_id: int) -> int:
    """Return total storage bytes for the tenant.

    Aggregates PostgreSQL schema size + WildDuck mail quota.
    Returns 0 silently on any error.
    """
    try:
        from hubra.core.services.storage_metrics import get_storage_bytes

        return get_storage_bytes(tenant_id)
    except Exception:
        return 0


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise TenantProvisioningError(
            f"Invalid slug '{slug}'. Must be 3-64 chars, lowercase, "
            "start/end with alphanumeric, hyphens allowed in between."
        )


def _seed_tenant(
    tenant_id: int,
    admin_email: str | None,
    admin_password: str | None,
    admin_user_id: int | None = None,
) -> None:
    """Seed default data into a freshly-created tenant schema.

    Creates:
      - 4 system roles: Owner, Admin, Treasurer, Member
      - Maker membership tier (free)
      - system.initialized setting
      - Admin User (public schema) + Member (tenant schema) + UserTenant link
        with is_owner=True — when admin_email and admin_password are provided.
      - Existing User linked as Owner Member + UserTenant with is_owner=True
        — when admin_user_id is provided (tenant-request approval path).
    """
    from .context import set_search_path, reset_search_path

    set_search_path(tenant_id)

    try:
        from hubra.core.models.role import Role
        from hubra.core.models.member import Member, MembershipTier

        role_defs = [
            {
                "name": "Owner",
                "is_admin": True,
                "is_default": False,
                "is_system": True,
                "is_owner": True,
                "description": "Full access — system role, un-lockoutable, always >=1 per tenant",
            },
            {
                "name": "Admin",
                "is_admin": True,
                "is_default": False,
                "is_system": True,
                "is_owner": False,
                "description": "Manage all features except roles deletion and global settings",
            },
            {
                "name": "Treasurer",
                "is_admin": False,
                "is_default": False,
                "is_system": True,
                "is_owner": False,
                "description": "Manage finances, view members and audit logs",
            },
            {
                "name": "Member",
                "is_admin": False,
                "is_default": True,
                "is_system": True,
                "is_owner": False,
                "description": "Basic member access — read-only on public resources",
            },
        ]
        roles: dict[str, Role] = {}
        for rd in role_defs:
            role = Role(**rd)
            db.session.add(role)
            db.session.flush()
            roles[rd["name"]] = role

        _ROLE_PERMS: dict[str, list[str]] = {
            "Treasurer": [
                "finance.transactions.read",
                "finance.transactions.create",
                "finance.transactions.update",
                "finance.transactions.delete",
                "finance.invoices.read",
                "finance.invoices.create",
                "finance.invoices.update",
                "finance.invoices.delete",
                "finance.invoices.remind",
                "finance.invoices.read_reminders",
                "finance.overview.read",
                "finance.transaction_categories.read",
                "finance.transaction_categories.create",
                "finance.transaction_categories.update",
                "finance.transaction_categories.delete",
                "finance.external_parties.read",
                "finance.external_parties.create",
                "finance.external_parties.update",
                "finance.external_parties.delete",
                "members.members.read",
                "tiers.tiers.read",
                "tiers.tiers.calculate_cost",
                "tiers.tiers.read_members",
                "audit.audit.read",
                "dashboard.dashboard.read",
            ],
            "Member": [
                "members.members.read",
                "groups.groups.read",
                "events.events.read",
                "polls.polls.read",
                "polls.polls.vote",
                "posts.posts.read",
                "posts.posts.like",
                "posts.posts.comment",
                "dashboard.dashboard.read",
                "notifications.notifications.read",
            ],
        }
        from hubra.api.roles.services import RoleService

        for role_name, perm_keys in _ROLE_PERMS.items():
            role = roles.get(role_name)
            if role is None:
                continue
            from hubra.core.models.role import RolePermission

            existing_keys = {
                p.permission_id
                for p in db.session.scalars(
                    select(RolePermission).where(RolePermission.role_id == role.id)
                ).all()
            }
            if not existing_keys:
                RoleService.set_permissions(
                    role, perm_keys, actor_id=None, _internal=True
                )

        tier = MembershipTier(
            name="Maker",
            price_chf=Decimal(0),
            color="#6366f1",
        )
        db.session.add(tier)
        db.session.flush()

        # Give the club its own switch for every optional module, set to the
        # manifest default, so catalog defaults never leak into new clubs.
        reset_search_path()
        from hubra.core.models.feature import TenantFeature
        from hubra.core.modules import registry, sync_catalog

        sync_catalog()
        for module in registry.all():
            if not module.required:
                db.session.add(
                    TenantFeature(
                        tenant_id=tenant_id,
                        feature_code=module.code,
                        enabled=module.default_enabled,
                    )
                )
        db.session.flush()
        set_search_path(tenant_id)

        if admin_email and admin_password:
            from hubra.core.models.user import User
            from hubra.core.models.user_tenant import UserTenant

            name_parts = admin_email.split("@")[0].split(".", 1)
            user = User(
                email=admin_email,
                first_name=name_parts[0].capitalize() if name_parts else "Admin",
                last_name=name_parts[1].capitalize() if len(name_parts) > 1 else "",
            )
            user.set_password(admin_password)
            db.session.add(user)
            db.session.flush()

            member = Member(
                tier_id=tier.id,
                user_id=user.id,
                status="active",
            )
            member.roles = [roles["Owner"]]
            db.session.add(member)
            db.session.flush()

            reset_search_path()
            db.session.add(
                UserTenant(
                    user_id=user.id,
                    tenant_id=tenant_id,
                    status="active",
                    is_owner=True,
                )
            )
        elif admin_user_id is not None:
            from hubra.core.models.user import User
            from hubra.core.models.user_tenant import UserTenant

            user = db.session.get(User, admin_user_id)
            if user is None:
                reset_search_path()
                raise TenantProvisioningError(f"User id={admin_user_id} not found")

            member = Member(
                tier_id=tier.id,
                user_id=user.id,
                status="active",
            )
            member.roles = [roles["Owner"]]
            db.session.add(member)
            db.session.flush()

            reset_search_path()
            existing_link = db.session.scalar(
                select(UserTenant).where(
                    UserTenant.user_id == user.id,
                    UserTenant.tenant_id == tenant_id,
                )
            )
            if existing_link is None:
                db.session.add(
                    UserTenant(
                        user_id=user.id,
                        tenant_id=tenant_id,
                        status="active",
                        is_owner=True,
                    )
                )
        else:
            reset_search_path()

        _log.info("Tenant %d seeded (admin=%s)", tenant_id, admin_email)
    except Exception:
        reset_search_path()
        raise
