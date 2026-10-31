"""
Application factory for the Hubra backend.

Usage:
    from hubra import create_app
    app = create_app()               # uses FLASK_ENV env var
    app = create_app("testing")      # explicit config name
"""

from __future__ import annotations

import os
import time

import click
from flask import Flask, jsonify, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import select

from .config import config_map
from .extensions import db, migrate, jwt, ma, cors, limiter
from .errors import api_error, register_error_handlers
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

    from hubra.core.tasks.session_tasks import update_last_seen

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


def _reject_scalar_json():
    """Endpoints read a JSON object (a few a list); a bare string or number
    would reach ``body.get(...)`` and fail with a 500."""
    if request.method in ("POST", "PUT", "PATCH") and request.is_json:
        body = request.get_json(silent=True)
        if isinstance(body, (str, int, float, bool)):
            return api_error(
                "VALIDATION_ERROR", "Request body must be a JSON object", 400
            )
    return None


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

    # __name__ is now 'hubra.core.app' instead of 'hubra',
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
    from hubra.core.tenant.context import install_search_path_guard
    from hubra.core.tenant.middleware import TenantPathMiddleware, resolve_tenant

    install_search_path_guard()

    app.wsgi_app = TenantPathMiddleware(app.wsgi_app)
    app.before_request(_reject_scalar_json)
    app.before_request(resolve_tenant)

    limiter.init_app(app)

    # ── Structured JSON logging ───────────────────────────────────────────────
    from .logging_config import configure_logging

    configure_logging(app)

    # ── Per-tenant API call counting ──────────────────────────────────────────
    from hubra.api.metrics import configure_api_counting

    configure_api_counting(app)

    # ── Import all models so SQLAlchemy can configure mappers ─────────────────
    import hubra.core.models  # noqa: F401

    # ── Register JWT callbacks (blocklist + user lookup) ──────────────────────
    try:
        from hubra.api.auth.routes import register_jwt_callbacks

        register_jwt_callbacks(jwt)
    except ModuleNotFoundError as exc:
        if exc.name and not exc.name.startswith("hubra"):
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
                    from hubra.api.auth.helpers import (
                        parse_identity,
                        is_user_identity,
                    )

                    if is_user_identity(identity):
                        _maybe_dispatch_last_seen(parse_identity(identity))
                    else:
                        # Legacy token: resolve member → user_id
                        from hubra.core.extensions import db
                        from hubra.core.models.member import Member

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
    # after_request hooks run in reverse order, so this must be registered
    # before flask-cors to see the Access-Control-Allow-Origin it sets.
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

    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
            # The SPA sends the active club on every request (api-client).
            "X-Tenant-Slug",
        ],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        expose_headers=[
            "Content-Disposition",
            "X-Total-Count",
        ],
        max_age=600,
    )
    app.logger.info("CORS origins: %s", app.config["CORS_ORIGINS"])

    # ── Modules: blueprints and the per-tenant gate ──────────────────────────
    from hubra.core.modules import module_gate, registry

    with app.app_context():
        registry.load()
        from hubra.core.plugins import loader as plugin_loader

        app.extensions["hubra.plugins"] = plugin_loader.current()
    registry.register_blueprints(app)
    # Registered after resolve_tenant, so g.tenant is known here.
    app.before_request(module_gate)

    # ── Root health endpoint (for Docker healthcheck) ──────────────────────────
    @app.get("/health")
    @limiter.exempt
    def _root_health():
        from hubra.api.health.cache import HealthCache

        cached = HealthCache.get()
        if cached is None:
            return jsonify({"status": "degraded"}), 200
        overall = cached.get("status", "degraded")
        http_status = 200 if overall in ("ok", "degraded") else 503
        return jsonify({"status": overall}), http_status

    # ── Register CLI commands ─────────────────────────────────────────────────
    _register_cli(app)

    return app


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

        from hubra.core.seeds import run_seeds

        run_seeds(db)
        click.echo("Seed data inserted.")

    from hubra.core.plugins.cli import register as register_plugin_cli

    register_plugin_cli(app)

    @app.cli.group("modules")
    def modules_cli():
        """List and switch modules per club."""

    def _tenant_id(slug: str | None) -> int | None:
        if slug is None:
            return None
        from hubra.core.models.tenant import Tenant

        tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
        if tenant is None:
            raise click.ClickException(f"Tenant '{slug}' not found")
        return tenant.id

    @modules_cli.command("sync")
    def modules_sync():
        """Write one catalog row per module manifest."""
        from hubra.core.modules import sync_catalog

        created = sync_catalog()
        db.session.commit()
        click.echo(f"Module catalog synced ({created} new).")

    @modules_cli.command("seal-secrets")
    def modules_seal_secrets():
        """Encrypt secret module settings still stored in the clear."""
        from hubra.core.modules.state import seal_secrets

        count = seal_secrets()
        db.session.commit()
        click.echo(f"Encrypted {count} secret setting(s).")

    @modules_cli.command("list")
    @click.option("--tenant", "slug", help="Tenant slug (default: no tenant)")
    def modules_list(slug: str | None):
        """Show every module and whether it is on."""
        from hubra.core.modules import states

        for code, st in states(_tenant_id(slug)).items():
            flag = "on " if st.effective else "off"
            note = ""
            if not st.allowed:
                note = " (blocked by manager)"
            elif st.missing_dependencies:
                note = f" (needs {', '.join(st.missing_dependencies)})"
            elif st.module.required:
                note = " (required)"
            click.echo(f"{flag} {code:<20} {st.module.name}{note}")

    @modules_cli.command("enable")
    @click.argument("code")
    @click.option("--tenant", "slug", help="Tenant slug (default: no tenant)")
    def modules_enable(code: str, slug: str | None):
        from hubra.core.modules import set_enabled

        set_enabled(code, True, _tenant_id(slug))
        db.session.commit()
        click.echo(f"{code} switched on.")

    @modules_cli.command("disable")
    @click.argument("code")
    @click.option("--tenant", "slug", help="Tenant slug (default: no tenant)")
    def modules_disable(code: str, slug: str | None):
        from hubra.core.modules import set_enabled

        set_enabled(code, False, _tenant_id(slug))
        db.session.commit()
        click.echo(f"{code} switched off.")

    @app.cli.command("create-tables")
    def create_tables():
        """Create all database tables (dev helper, prefer flask db upgrade in prod)."""
        db.create_all()
        click.echo("All tables created.")

    @app.cli.command("seed-global-rbac")
    def seed_global_rbac_cmd():
        """Seed default global roles and permissions for the manager portal."""
        from hubra.api.global_rbac_seed import seed_global_rbac

        seed_global_rbac()
        click.echo("Global RBAC seed complete.")

    @app.cli.command("cleanup-webhooks")
    def cleanup_webhooks():
        """Remove any lingering WildDuck webhooks (post-migration cleanup)."""
        from hubra.core.services.wildduck import get_client

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
        from hubra.core.services.wildduck import get_client

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
        from hubra.core.tenant.service import TenantService, TenantProvisioningError

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
        from hubra.core.tenant.service import TenantService

        tenants = TenantService.list_tenants(per_page=10_000)["tenants"]
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
        from hubra.core.models.user import User
        from hubra.core.models.member import Member
        from hubra.core.models.role import Role

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

    @app.cli.command("ensure-superadmins")
    @click.option(
        "--emails",
        envvar="SUPERADMIN_EMAILS",
        default="",
        help="Comma-separated login emails (default: env SUPERADMIN_EMAILS)",
    )
    def ensure_superadmins(emails: str):
        """Make the listed accounts superadmins. Never demotes anyone.

        Safe to run on every start (the init job does): unknown emails are
        skipped with a warning, so the account can sign up later.
        """
        from hubra.core.models.user import User

        wanted = [e.strip().lower() for e in emails.split(",") if e.strip()]
        for email in wanted:
            user = db.session.scalar(select(User).where(User.email == email))
            if user is None:
                click.echo(f"  WARNING: no account for {email} yet, skipped.", err=True)
            elif not user.is_superadmin:
                user.is_superadmin = True
                click.echo(f"  {email} is now superadmin.")
        db.session.commit()

    @app.cli.command("apply-tenant-migrations")
    @click.option(
        "--slug",
        default=None,
        help="Apply migrations to a specific tenant (default: all active)",
    )
    def apply_tenant_migrations(slug):
        """Apply pending Alembic migrations to tenant schemas."""
        from hubra.core.tenant.migration import (
            apply_migrations_to_tenant,
            apply_migrations_to_all_tenants,
        )

        if slug:
            from hubra.core.tenant.service import TenantService

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
        from hubra.api.permissions import EXTRA_PERMISSIONS, _derive_perm_key
        from hubra.api.fields import iter_field_perms
        from hubra.core.models.role import Permission

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
        for meta in EXTRA_PERMISSIONS:
            discovered[meta["key"]] = dict(meta)

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
        from hubra.api.permissions import invalidate_role_permissions
        from hubra.core.models.role import RolePermission, Permission

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
