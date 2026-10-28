"""Finance: transactions, categories, external parties and QR-bill invoices."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="finance",
    name="Finance",
    description="Transactions, invoices with Swiss QR-bill, and reminders",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.finance.routes",
            "finance_bp",
            "/api/v1/finance",
        ),
    ),
    nav=(
        NavItem(
            "/app/finance",
            "shell.nav.finance",
            "wallet",
            section="operations",
            order=0,
            perms=(
                "finance.overview.read",
                "finance.transactions.read",
                "finance.invoices.read",
                "finance.transaction_categories.read",
            ),
        ),
    ),
    tables=(
        "transactions",
        "invoices",
        "transaction_categories",
        "external_parties",
        "invoice_reminder_history",
        "qrr_references",
    ),
)
