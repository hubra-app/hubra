"""
Application factory for the Club Management Suite backend.

Usage:
    from vollbuild import create_app
    app = create_app()               # uses FLASK_ENV env var
    app = create_app("testing")      # explicit config name
"""

from __future__ import annotations

import os
import time

import click
from flask import Flask, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import select

from .config import config_map
from .extensions import db, migrate, jwt, ma, cors, limiter
from .errors import register_error_handlers
from .settings_loader import load_settings


_LAST_SEEN_THROTTLE_S = 60.0
_last_seen_cache: dict[int, float] = {}


def _maybe_dispatch_last_seen(member_id: int) -> None:
    """Dispatch a Celery task to update Member.last_seen, throttled per-worker.

    Skips the dispatch if *member_id* was updated less than
    ``_LAST_SEEN_THROTTLE_S`` seconds ago on this worker.
    In testing mode, runs synchronously to avoid broker connection hangs.
    """
    now = time.monotonic()
    last = _last_seen_cache.get(member_id)
    if last is not None and (now - last) < _LAST_SEEN_THROTTLE_S:
        return
    _last_seen_cache[member_id] = now
    from flask import current_app

    from vollbuild.core.tasks.session_tasks import update_last_seen

    if current_app.config.get("TESTING"):
        update_last_seen.run(member_id)
    else:
        update_last_seen.delay(member_id)


def _resolve_rate_limit_storage(app: Flask) -> str:
    """Probe Redis, fall back to memory storage if unreachable."""
    uri = app.config.get("RATELIMIT_STORAGE_URI", "memory://")
    if uri and not uri.startswith("memory"):
        try:
            import redis as redis_lib

            client = redis_lib.from_url(uri, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            client.close()
        except Exception:
            app.logger.warning(
                "Redis unreachable for rate limiting — falling back to memory storage"
            )
            return "memory://"
    return uri


def create_app(config_name: str | None = None) -> Flask:
    """
    Application factory.

    Args:
        config_name: One of "development", "production", "testing".
                     Defaults to the FLASK_ENV environment variable,
                     falling back to "development".

    Returns:
        A fully configured Flask application instance.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    # __name__ is now 'vollbuild.core.app' instead of 'vollbuild',
    # so we must point template/static folders back to the package root.
    import pathlib as _pathlib

    _pkg_root = str(_pathlib.Path(__file__).resolve().parent.parent)
    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder=_pkg_root + "/templates",
        static_folder=_pkg_root + "/static",
    )
    app.url_map.strict_slashes = False

    # ── Load configuration ────────────────────────────────────────────────────
    cfg_class = config_map.get(config_name, config_map["development"])
    if hasattr(cfg_class, "validate"):
        cfg_class.validate()
    app.config.from_object(cfg_class)
    load_settings(
        app
    )  # merge settings.yaml (env vars already set above take precedence)

    # ── Strip SQLite-incompatible engine options ──────────────────────────────
    _db_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    if "sqlite" in _db_uri:
        _opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
        for _pool_key in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle"):
            _opts.pop(_pool_key, None)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = _opts

    # ── Resolve rate-limit storage (probe Redis, fall back to memory) ─────────
    app.config["RATELIMIT_STORAGE_URI"] = _resolve_rate_limit_storage(app)

    # ── Initialise extensions ─────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)

    # ── Register tenant resolver middleware ───────────────────────────────────
    from vollbuild.core.tenant.middleware import resolve_tenant

    app.before_request(resolve_tenant)

    limiter.init_app(app)

    # ── Structured JSON logging ───────────────────────────────────────────────
    from .logging_config import configure_logging

    configure_logging(app)

    # ── Per-tenant API call counting ──────────────────────────────────────────
    from vollbuild.api.metrics import configure_api_counting

    configure_api_counting(app)

    # ── Import all models so SQLAlchemy can configure mappers ─────────────────
    import vollbuild.core.models  # noqa: F401

    # ── Register JWT callbacks (blocklist + user lookup) ──────────────────────
    try:
        from vollbuild.api.auth.routes import register_jwt_callbacks

        register_jwt_callbacks(jwt)
    except ModuleNotFoundError as exc:
        if exc.name and not exc.name.startswith("vollbuild"):
            raise
        app.logger.debug("Auth module not yet available, JWT callbacks not registered")

    # ── Register error handlers ───────────────────────────────────────────────
    register_error_handlers(app)

    # ── Security headers (HSTS, X-Frame-Options, X-Content-Type-Options) ──────
    @app.after_request
    def _add_security_headers(response):
        # Dispatch last_seen update asynchronously (throttled per-worker).
        # Must not prevent headers being set even if JWT lookup fails.
        if response.status_code < 400:
            try:
                identity = get_jwt_identity()
                if identity is not None:
                    from vollbuild.api.auth.helpers import (
                        parse_identity,
                        is_user_identity,
                    )

                    if is_user_identity(identity):
                        _maybe_dispatch_last_seen(parse_identity(identity))
                    else:
                        # Legacy token: resolve member → user_id
                        from vollbuild.core.extensions import db
                        from vollbuild.core.models.member import Member

                        member = db.session.get(Member, int(identity))
                        if member and member.user_id:
                            _maybe_dispatch_last_seen(member.user_id)
            except Exception:
                app.logger.debug("last_seen dispatch skipped", exc_info=True)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # ── CORS ──────────────────────────────────────────────────────────────
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
        ],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        expose_headers=[
            "Content-Disposition",
            "X-Total-Count",
        ],
        max_age=600,
    )
    app.logger.info("CORS origins: %s", app.config["CORS_ORIGINS"])

    @app.after_request
    def _ensure_vary_origin(response):
        acao = response.headers.get("Access-Control-Allow-Origin")
        if acao and acao != "*":
            existing = response.headers.get("Vary")
            if existing:
                parts = [p.strip() for p in existing.split(",") if p.strip()]
                if "Origin" not in parts and "origin" not in parts:
                    response.headers["Vary"] = ", ".join([*parts, "Origin"])
            else:
                response.headers["Vary"] = "Origin"
        return response

    # ── Register blueprints ───────────────────────────────────────────────────
    _register_blueprints(app)

    # ── Register v2 namespace blueprints ───────────────────────────────────────
    from vollbuild.apps.global_.routes import register_global_v2
    from vollbuild.apps.manager.routes import register_manager_v2
    from vollbuild.apps.tenants.routes import register_tenants_v2

    register_global_v2(app)
    register_manager_v2(app)
    register_tenants_v2(app)

    # ── Root health endpoint (for Docker healthcheck) ──────────────────────────
    @app.get("/health")
    @limiter.exempt
    def _root_health():
        from vollbuild.api.health.cache import HealthCache

        cached = HealthCache.get()
        if cached is None:
            return jsonify({"status": "degraded"}), 200
        overall = cached.get("status", "degraded")
        http_status = 200 if overall in ("ok", "degraded") else 503
        return jsonify({"status": overall}), http_status

    # ── Register CLI commands ─────────────────────────────────────────────────
    _register_cli(app)

    return app


# ── Blueprint registration ────────────────────────────────────────────────────

_BLUEPRINT_SPECS = [
    # (import_path,      blueprint_name,  url_prefix)
    ("vollbuild.api.auth.routes", "auth_bp", "/api/v1/auth"),
    ("vollbuild.api.auth.routes", "account_bp", "/api/v1/account"),
    ("vollbuild.api.members.routes", "members_bp", "/api/v1/members"),
    ("vollbuild.api.applications.routes", "applications_bp", "/api/v1/applications"),
    ("vollbuild.api.groups.routes", "groups_bp", "/api/v1/groups"),
    ("vollbuild.api.functions.routes", "functions_bp", "/api/v1/functions"),
    ("vollbuild.api.events.routes", "events_bp", "/api/v1/events"),
    ("vollbuild.api.polls.routes", "polls_bp", "/api/v1/polls"),
    ("vollbuild.api.posts.routes", "posts_bp", "/api/v1/posts"),
    ("vollbuild.api.finance.routes", "finance_bp", "/api/v1/finance"),
    ("vollbuild.api.mail.routes", "mail_bp", "/api/v1/mail"),
    ("vollbuild.api.settings.routes", "settings_bp", "/api/v1/settings"),
    ("vollbuild.api.features.routes", "features_bp", "/api/v1/features"),
    ("vollbuild.api.bindings.routes", "bindings_bp", "/api/v1/bindings"),
    ("vollbuild.api.dashboard.routes", "dashboard_bp", "/api/v1/dashboard"),
    ("vollbuild.api.notifications.routes", "notifications_bp", "/api/v1/notifications"),
    ("vollbuild.api.roles.routes", "roles_bp", "/api/v1/roles"),
    ("vollbuild.api.tiers.routes", "tiers_bp", "/api/v1/tiers"),
    ("vollbuild.api.audit.routes", "audit_bp", "/api/v1/audit"),
    ("vollbuild.api.inventory.routes", "inventory_bp", "/api/v1/inventory"),
    ("vollbuild.api.health.routes", "health_bp", "/api/v1"),
    ("vollbuild.api.system.routes", "system_bp", "/api/v1/system"),
    ("vollbuild.api.i18n.routes", "i18n_bp", "/api/v1/i18n"),
    ("vollbuild.api.codes.routes", "codes_bp", "/api/v1/codes"),
    ("vollbuild.api.version.routes", "version_bp", "/api/v1"),
    ("vollbuild.api.backups.routes", "backups_bp", "/api/v1/backups"),
    ("vollbuild.api.tenant.routes", "tenant_admin_bp", "/api/v1/system"),
    ("vollbuild.api.admin.routes", "admin_bp", "/api/v1/admin"),
]


def _register_blueprints(app: Flask) -> None:
    """
    Attempt to import and register each domain blueprint.

    Blueprints that do not exist yet are silently skipped so the app can
    start even before all domain modules are implemented.
    """
    import importlib

    for module_path, bp_name, prefix in _BLUEPRINT_SPECS:
        try:
            module = importlib.import_module(module_path)
            blueprint = getattr(module, bp_name)
            app.register_blueprint(blueprint, url_prefix=prefix)
            app.logger.debug("Registered blueprint %s → %s", bp_name, prefix)
        except ModuleNotFoundError as exc:
            top_level = module_path.split(".")[0]
            if exc.name and not exc.name.startswith(top_level):
                raise  # a dependency inside the blueprint is broken
            app.logger.debug("Blueprint %s not yet implemented, skipping", module_path)
        except AttributeError:
            app.logger.warning(
                "Module '%s' does not expose '%s' — skipping.",
                module_path,
                bp_name,
            )


# ── CLI commands ──────────────────────────────────────────────────────────────


def _register_cli(app: Flask) -> None:
    """Attach custom flask CLI commands to *app*."""

    @app.cli.command("seed")
    @click.option("--drop", is_flag=True, help="Drop and recreate all tables first.")
    @click.option(
        "--skip-migrate",
        is_flag=True,
        help="Skip running migrations (use when already migrated).",
    )
    def seed_db(drop: bool, skip_migrate: bool):
        """Seed the database with initial / fixture data."""
        if drop:
            click.echo("Dropping all tables…")
            db.drop_all()

        if not skip_migrate:
            click.echo("Running migrations…")
            from flask_migrate import upgrade as db_upgrade

            db_upgrade()
            click.echo("Migrations complete.")

        from vollbuild.core.seeds import run_seeds

        run_seeds(db)
        click.echo("Seed data inserted.")

    @app.cli.command("create-tables")
    def create_tables():
        """Create all database tables (dev helper, prefer flask db upgrade in prod)."""
        db.create_all()
        click.echo("All tables created.")

    @app.cli.command("seed-global-rbac")
    def seed_global_rbac_cmd():
        """Seed default global roles and permissions for the manager portal."""
        from vollbuild.api.global_rbac_seed import seed_global_rbac

        seed_global_rbac()
        click.echo("Global RBAC seed complete.")

    @app.cli.command("cleanup-webhooks")
    def cleanup_webhooks():
        """Remove any lingering WildDuck webhooks (post-migration cleanup)."""
        from vollbuild.core.services.wildduck import get_client

        wd = get_client()
        existing = wd.list_webhooks()
        removed = 0
        for h in existing.get("results", []):
            wd.delete_webhook(h["id"])
            removed += 1
        click.echo(f"Removed {removed} webhook(s).")

    @app.cli.command("clear-mail-targets")
    def clear_mail_targets():
        """Clear legacy ``targets`` on all WildDuck users (migration helper)."""
        from vollbuild.core.services.wildduck import get_client

        wd = get_client()
        page = 1
        cleared = 0
        while True:
            users = wd.list_users(limit=250, page=page)
            results = users.get("results", [])
            if not results:
                break
            for user in results:
                uid = user.get("id")
                if uid:
                    wd.update_user(uid, targets=[])
                    cleared += 1
            page += 1
        click.echo(f"Cleared targets on {cleared} WildDuck user(s).")

    @app.cli.command("provision-tenant")
    @click.option("--name", required=True, help="Human-readable tenant name")
    @click.option("--slug", required=True, help="URL-safe tenant slug")
    @click.option(
        "--plan", default="starter", help="Plan (starter / growth / enterprise)"
    )
    @click.option("--admin-email", default=None, help="Initial admin email")
    @click.option("--admin-password", default=None, help="Initial admin password")
    def provision_tenant(name, slug, plan, admin_email, admin_password):
        """Provision a new tenant (record + schema + seed)."""
        from vollbuild.core.tenant.service import TenantService, TenantProvisioningError

        try:
            tenant = TenantService.provision_tenant(
                name=name,
                slug=slug,
                plan=plan,
                admin_email=admin_email,
                admin_password=admin_password,
            )
            click.echo(
                f"Tenant '{tenant.name}' provisioned (id={tenant.id}, slug={tenant.slug})"
            )
        except TenantProvisioningError as exc:
            click.echo(f"ERROR: {exc}", err=True)
            raise SystemExit(1) from exc

    @app.cli.command("list-tenants")
    def list_tenants():
        """List all tenants."""
        from vollbuild.core.tenant.service import TenantService

        tenants = TenantService.list_tenants()
        if not tenants:
            click.echo("No tenants found.")
            return
        for t in tenants:
            click.echo(
                f"  {t.id:>4}  {t.slug:<30}  {t.name:<40}  {t.status:<12}  {t.plan}"
            )

    @app.cli.command("make-admin")
    @click.option("--email", required=True, help="Login email of the user to promote")
    @click.option(
        "--superadmin/--no-superadmin",
        default=True,
        help="Set User.is_superadmin (default: yes)",
    )
    @click.option(
        "--tenant-admin/--no-tenant-admin",
        default=True,
        help="Assign Admin Role to the user's Member(s) (default: yes)",
    )
    def make_admin(email: str, superadmin: bool, tenant_admin: bool):
        """Promote an existing user to superadmin and/or tenant admin by email."""
        from vollbuild.core.models.user import User
        from vollbuild.core.models.member import Member
        from vollbuild.core.models.role import Role

        user = db.session.scalar(
            select(User).where(User.email == email.strip().lower())
        )
        if user is None:
            click.echo(f"ERROR: No User found with email '{email}'", err=True)
            raise SystemExit(1)

        if superadmin:
            if user.is_superadmin:
                click.echo(f"  User {email} is already superadmin.")
            else:
                user.is_superadmin = True
                click.echo(f"  Set User.is_superadmin = True for {email}.")

        if tenant_admin:
            admin_role = db.session.scalar(select(Role).where(Role.name == "Admin"))
            if admin_role is None:
                click.echo(
                    "  WARNING: 'Admin' Role not found — skipping tenant-admin.",
                    err=True,
                )
            else:
                members = db.session.scalars(
                    select(Member).where(
                        Member.user_id == user.id,
                        Member.archived_at.is_(None),
                    )
                ).all()
                if not members:
                    click.echo(f"  No active Member records linked to User {email}.")
                for m in members:
                    if admin_role not in m.roles:
                        m.roles.append(admin_role)
                        click.echo(
                            f"  Assigned Admin role to Member id={m.id} ({m.name})."
                        )
                    else:
                        click.echo(
                            f"  Member id={m.id} ({m.name}) already has Admin role."
                        )

        db.session.commit()
        click.echo(f"Done. User {email} updated.")

    @app.cli.command("apply-tenant-migrations")
    @click.option(
        "--slug",
        default=None,
        help="Apply migrations to a specific tenant (default: all active)",
    )
    def apply_tenant_migrations(slug):
        """Apply pending Alembic migrations to tenant schemas."""
        from vollbuild.core.tenant.migration import (
            apply_migrations_to_tenant,
            apply_migrations_to_all_tenants,
        )

        if slug:
            from vollbuild.core.tenant.service import TenantService

            tenant = TenantService.get_by_slug(slug)
            if tenant is None:
                click.echo(f"ERROR: Tenant with slug '{slug}' not found", err=True)
                raise SystemExit(1)
            apply_migrations_to_tenant(tenant.id)
            click.echo(f"Migrations applied to tenant '{slug}' (id={tenant.id})")
        else:
            count = apply_migrations_to_all_tenants()
            click.echo(f"Migrations applied to {count} active tenant(s).")

    @app.cli.command("sync-permissions")
    def sync_permissions():
        """Sync the Permission table with all @permission_required-decorated routes."""
        from vollbuild.api.permissions import _derive_perm_key
        from vollbuild.api.fields import iter_field_perms
        from vollbuild.core.models.role import Permission

        discovered: dict[str, dict] = {}
        for rule in app.url_map.iter_rules():
            fn = app.view_functions.get(rule.endpoint)
            if fn is None:
                continue
            resource = getattr(fn, "_perm_resource", None)
            action = getattr(fn, "_perm_action", None)
            if resource is None or action is None:
                continue
            bp_name = rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else None
            key = _derive_perm_key(bp_name, resource, action)
            display_name = getattr(fn, "_perm_display_name", f"{action} {resource}")
            discovered[key] = {
                "key": key,
                "display_name": display_name,
                "resource": resource,
                "action": action,
                "blueprint": bp_name or "",
            }

        existing = {p.key: p for p in db.session.scalars(select(Permission)).all()}

        # Add field-level perms to discovered so they aren't marked as orphaned
        for meta in iter_field_perms():
            discovered[meta["key"]] = meta

        created = 0
        updated = 0
        orphaned = 0

        for key, meta in discovered.items():
            perm = existing.get(key)
            if perm is None:
                db.session.add(
                    Permission(
                        key=meta["key"],
                        display_name=meta["display_name"],
                        resource=meta["resource"],
                        action=meta["action"],
                        blueprint=meta["blueprint"],
                        is_active=True,
                    )
                )
                created += 1
            else:
                changed = False
                if perm.display_name != meta["display_name"]:
                    perm.display_name = meta["display_name"]
                    changed = True
                if perm.resource != meta["resource"]:
                    perm.resource = meta["resource"]
                    changed = True
                if perm.action != meta["action"]:
                    perm.action = meta["action"]
                    changed = True
                if perm.blueprint != meta["blueprint"]:
                    perm.blueprint = meta["blueprint"]
                    changed = True
                if not perm.is_active:
                    perm.is_active = True
                    changed = True
                if changed:
                    updated += 1

        for key, perm in existing.items():
            if key not in discovered and perm.is_active:
                perm.is_active = False
                orphaned += 1

        db.session.commit()
        click.echo(
            f"Synced permissions: {created} created, {updated} updated, {orphaned} orphaned (deactivated)."
        )

    @app.cli.command("migrate-role-permissions")
    def migrate_role_permissions():
        """Migrate old free-text RolePermission strings to new Permission key references."""
        from vollbuild.api.permissions import invalidate_role_permissions
        from vollbuild.core.models.role import RolePermission, Permission

        old_to_new = {
            "View members": [
                "members.members.read",
                "tiers.tiers.read",
                "tiers.tiers.calculate_cost",
                "tiers.tiers.read_members",
            ],
            "Edit members": [
                "members.members.create",
                "members.members.update",
                "members.members.verify_email",
                "members.members.provision",
                "mail.member_mail.update",
            ],
            "Delete members": [
                "members.members.archive",
                "members.members.unarchive",
                "members.members.delete",
            ],
            "Manage members": [
                "members.members.disable",
                "members.members.enable",
                "members.members.set_password",
            ],
            "Export data": [
                "members.members.export",
            ],
            "View finances": [
                "finance.transaction_categories.read",
                "finance.transactions.read",
                "finance.invoices.read",
                "finance.overview.read",
                "finance.external_parties.read",
            ],
            "Record transactions": [
                "finance.transaction_categories.create",
                "finance.transaction_categories.update",
                "finance.transaction_categories.delete",
                "finance.transactions.create",
                "finance.transactions.update",
                "finance.transactions.delete",
                "finance.external_parties.create",
                "finance.external_parties.update",
                "finance.external_parties.delete",
            ],
            "Manage invoices": [
                "finance.invoices.create",
                "finance.invoices.update",
                "finance.invoices.delete",
                "finance.invoices.bulk_create",
                "finance.invoices.remind",
                "finance.invoices.read_reminders",
            ],
            "View groups": [
                "groups.groups.read",
                "events.events.read",
                "polls.polls.read",
                "polls.polls.vote",
                "posts.posts.read",
                "posts.posts.like",
                "posts.posts.comment",
            ],
            "Manage groups": [
                "groups.groups.create",
                "groups.groups.update",
                "groups.groups.delete",
                "groups.groups.add_member",
                "groups.groups.remove_member",
            ],
            "Manage events": [
                "events.events.create",
                "events.events.update",
                "events.events.delete",
                "events.events.add_attendee",
                "events.events.remove_attendee",
            ],
            "Manage polls": [
                "polls.polls.create",
                "polls.polls.update",
                "polls.polls.close",
                "polls.polls.delete",
            ],
            "Manage posts": [
                "posts.posts.create",
                "posts.posts.update",
                "posts.posts.delete",
                "posts.posts.like",
                "posts.posts.comment",
            ],
            "View inventory": [
                "inventory.items.read",
            ],
            "Manage inventory": [
                "inventory.items.create",
                "inventory.items.update",
                "inventory.items.delete",
                "inventory.items.manage_instructions",
            ],
            "Approve applications": [
                "applications.applications.read",
                "applications.applications.approve",
                "applications.applications.decline",
                "applications.applications.delete",
            ],
            "Manage roles": [
                "roles.roles.create",
                "roles.roles.update",
                "roles.roles.delete",
                "roles.roles.set_permissions",
            ],
            "Manage tiers": [
                "tiers.tiers.create",
                "tiers.tiers.update",
                "tiers.tiers.delete",
            ],
            "Audit log": [
                "audit.audit.read",
            ],
            "General settings": [
                "settings.settings.read",
                "settings.settings.write",
                "settings.settings.delete",
            ],
            "View mailboxes": [
                "mail.mailboxes.read",
                "mail.aliases.read",
                "mail.member_mail.read",
                "mail.wildduck.read",
            ],
            "Manage mailboxes": [
                "mail.mailboxes.create",
                "mail.mailboxes.update",
                "mail.mailboxes.delete",
                "mail.aliases.create",
                "mail.aliases.update",
                "mail.aliases.delete",
                "mail.wildduck.delete",
                "mail.reconcile.run",
            ],
            "Send test email": [
                "mail.test_email.send",
            ],
        }

        # Build a lookup of Permission rows by key
        perm_by_key = {p.key: p for p in db.session.scalars(select(Permission)).all()}

        # Find all old-style RolePermission rows with a non-null permission string
        old_rows = db.session.scalars(
            select(RolePermission).where(RolePermission.permission.isnot(None))
        ).all()

        migrated = 0
        skipped = 0
        errors = 0

        for row in old_rows:
            old_perm = row.permission
            new_keys = old_to_new.get(old_perm, [])
            if not new_keys:
                click.echo(
                    f"  WARNING: No mapping for old permission '{old_perm}' (role_id={row.role_id})"
                )
                errors += 1
                continue

            for new_key in new_keys:
                perm = perm_by_key.get(new_key)
                if perm is None:
                    click.echo(
                        f"  WARNING: Permission key '{new_key}' not in DB — run 'flask sync-permissions' first"
                    )
                    errors += 1
                    continue

                # Check if this role→permission link already exists
                existing = db.session.scalar(
                    select(RolePermission.id)
                    .where(RolePermission.role_id == row.role_id)
                    .where(RolePermission.permission_id == perm.id)
                )
                if existing is None:
                    db.session.add(
                        RolePermission(role_id=row.role_id, permission_id=perm.id)
                    )
                    migrated += 1
                else:
                    skipped += 1

            invalidate_role_permissions(row.role_id)

        db.session.commit()
        click.echo(
            f"Migrated: {migrated} created, {skipped} already existed, {errors} errors."
        )
