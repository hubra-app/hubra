"""Finance: transactions, categories, external parties and QR-bill invoices."""

from hubra.core.modules import Blueprint, Module, NavItem, SettingField

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
    settings=(
        SettingField(
            "payment_term_days",
            "int",
            default=30,
            label="Payment term (days)",
            description="Due date of generated invoices, and of bulk invoices without a date",
        ),
        SettingField(
            "email_new_invoices",
            "bool",
            default=True,
            label="Email new invoices to members",
            description="With the QR-bill attached",
        ),
        SettingField(
            "reminders_enabled",
            "bool",
            default=True,
            label="Send payment reminders",
        ),
        SettingField(
            "first_reminder_days",
            "int",
            default=7,
            label="First reminder (days after due)",
        ),
        SettingField(
            "second_reminder_days",
            "int",
            default=14,
            label="Second reminder (days after due)",
        ),
        SettingField(
            "bill_on_join_date",
            "bool",
            default=False,
            label="Bill each member on their join date",
            description="Otherwise everyone is billed on the billing date below",
        ),
        SettingField(
            "fee_anchor_month",
            "int",
            default=1,
            label="Billing date: month",
        ),
        SettingField(
            "fee_anchor_day",
            "int",
            default=1,
            label="Billing date: day",
        ),
        SettingField(
            "prorate_first_fee",
            "bool",
            default=True,
            label="Reduce the first fee for members who join during the year",
            description="By the months left, the join month counting in full",
        ),
        SettingField(
            "statement_enabled",
            "bool",
            default=False,
            label="Mail an account statement every month",
            description="On the 1st, for the month before, as a PDF",
        ),
        SettingField(
            "statement_email",
            "email",
            default="",
            label="Account statement goes to",
        ),
    ),
    nav=(
        NavItem(
            "/app/finance",
            "shell.nav.finance",
            "wallet",
            order=50,
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
        "recurring_transactions",
    ),
)
