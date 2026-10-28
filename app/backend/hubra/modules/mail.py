"""Mail: club mailboxes and aliases on the self-hosted mail stack."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="mail",
    name="Mail",
    description="Club mailboxes and aliases (needs the self-hosted mail stack)",
    default_enabled=False,
    depends_on=("members", "groups"),
    blueprints=(
        Blueprint(
            "hubra.api.mail.routes",
            "mail_bp",
            "/api/v1/mail",
            v2=(("/api/v2/tenants/mail", "mail_bp_v2"),),
        ),
    ),
    public_endpoints=("mail_bp.mail_health",),
    nav=(
        NavItem(
            "/app/mail",
            "shell.nav.mail",
            "mail",
            section="operations",
            order=10,
            perms=(
                "mail.mailboxes.read",
                "mail.aliases.read",
                "mail.system.read",
                "mail.member_mail.read",
                "mail.wildduck.read",
            ),
        ),
    ),
    tables=("managed_mail_addresses", "mailbox_folders"),
)
