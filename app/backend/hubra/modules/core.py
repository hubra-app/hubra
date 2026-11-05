"""Core: sign-in, accounts, settings, dashboard, audit and platform admin."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="core",
    name="Core",
    description="Sign-in, accounts, settings, dashboard, audit log and notifications",
    required=True,
    blueprints=(
        Blueprint(
            "hubra.api.auth.routes",
            "auth_bp",
            "/api/v1/global/auth",
        ),
        Blueprint(
            "hubra.api.auth.redirect_loop",
            "redirect_loop_bp",
            "/api/v1/global/auth",
        ),
        Blueprint(
            "hubra.api.auth.routes",
            "account_bp",
            "/api/v1/global/account",
        ),
        Blueprint(
            "hubra.api.settings.routes",
            "settings_bp",
            "/api/v1/app/settings",
        ),
        Blueprint(
            "hubra.api.features.routes",
            "features_bp",
            "/api/v1/app/features",
        ),
        Blueprint(
            "hubra.api.features.routes",
            "modules_bp",
            "/api/v1/app/modules",
        ),
        Blueprint("hubra.api.apps.routes", "apps_bp", "/api/v1/global/apps"),
        Blueprint(
            "hubra.api.auth.linked_accounts",
            "linked_accounts_bp",
            "/api/v1/global/account/linked-accounts",
        ),
        Blueprint(
            "hubra.api.dashboard.routes",
            "dashboard_bp",
            "/api/v1/app/dashboard",
        ),
        Blueprint(
            "hubra.api.notifications.routes",
            "notifications_bp",
            "/api/v1/app/notifications",
        ),
        Blueprint(
            "hubra.api.audit.routes",
            "audit_bp",
            "/api/v1/app/audit",
        ),
        Blueprint(
            "hubra.api.health.routes",
            "health_bp",
            "/api/v1/global",
        ),
        Blueprint(
            "hubra.api.system.routes",
            "system_bp",
            "/api/v1/app",
        ),
        Blueprint(
            "hubra.api.i18n.routes",
            "i18n_bp",
            "/api/v1/global/i18n",
        ),
        Blueprint(
            "hubra.api.version.routes",
            "version_bp",
            "/api/v1/global",
        ),
        Blueprint(
            "hubra.api.tenant.routes",
            "tenant_admin_bp",
            "/api/v1/platform/system",
        ),
        # The person's own side of /system: club directory, invites, join
        # and club requests, ending a support session (api_areas.py).
        Blueprint(
            "hubra.api.tenant.routes",
            "club_access_bp",
            "/api/v1/global",
        ),
        Blueprint(
            "hubra.api.admin.routes",
            "admin_bp",
            "/api/v1/app/admin",
        ),
        Blueprint(
            "hubra.api.plugins.routes",
            "plugins_bp",
            "/api/v1/platform/plugins",
        ),
        Blueprint("hubra.api.plugins.routes", "plugin_assets_bp", "/api/v1/global/plugins"),
        Blueprint(
            "hubra.api.platform.routes",
            "platform_bp",
            "/api/v1/platform",
        ),
        Blueprint("hubra.api.support.routes", "support_bp", "/api/v1/global/support"),
        Blueprint("hubra.api.support.routes", "roadmap_bp", "/api/v1/global/roadmap"),
        Blueprint(
            "hubra.api.support.routes",
            "support_admin_bp",
            "/api/v1/platform/support",
        ),
        Blueprint(
            "hubra.api.api_tokens.routes",
            "api_tokens_bp",
            "/api/v1/app/api-tokens",
        ),
        Blueprint(
            "hubra.api.api_tokens.routes",
            "platform_api_tokens_bp",
            "/api/v1/platform/api-tokens",
        ),
        Blueprint(
            "hubra.api.api_tokens.routes",
            "api_token_self_bp",
            "/api/v1",
        ),
        # OAuth for outside apps (docs/oauth.md). The server metadata sits at
        # the root of the API host (RFC 8414); roles.SHARED_PATHS lets every
        # backend answer it.
        Blueprint("hubra.api.oauth.routes", "oauth_metadata_bp", ""),
        Blueprint("hubra.api.oauth.routes", "oauth_bp", "/api/v1/global/oauth"),
        Blueprint(
            "hubra.api.oauth.routes",
            "platform_oauth_bp",
            "/api/v1/platform/oauth",
        ),
        Blueprint(
            "hubra.api.backups.routes",
            "platform_backups_bp",
            "/api/v1/platform/backups",
        ),
    ),
    nav=(
        NavItem("/app/dashboard", "shell.nav.dashboard", "dashboard", order=0),
        NavItem(
            "/app/settings",
            "shell.nav.settings",
            "settings",
            section="system",
            order=0,
            # settings.settings.read stands for an admin role (the API
            # checks is_admin); a role that switches modules or connects
            # apps sees that tab.
            perms=(
                "settings.settings.read",
                "modules.modules.write",
                "apps.apps.manage",
            ),
        ),
        NavItem(
            "/app/audit-log",
            "shell.nav.auditLog",
            "shield",
            section="system",
            order=10,
            perms=("audit.audit.read",),
            parent="/app/settings",
        ),
        NavItem(
            "/app/translations",
            "shell.nav.translations",
            "globe",
            section="more",
            order=30,
            perms=("i18n.i18n.write",),
        ),
        NavItem(
            "/app/account/settings",
            "shell.nav.accountSettings",
            "user",
            section="me",
            order=0,
        ),
    ),
    tables=(
        "setting",
        "notifications",
        "audit_entries",
        "token_blocklist",
        "devices",
        "sessions",
        "password_reset_tokens",
        "internal_keys",
    ),
)
