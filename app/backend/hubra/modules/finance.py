"""Finance: QR-bill invoices, reminders, fees and external parties.

The books (transactions, categories, the overview, recurring bookings, the
monthly statement and the annual accounts) are the Finances plugin, module
``finance.books``. Its tables stay listed here: invoices point at their
booking, so they live in every club schema either way.
"""

from hubra.core.contracts import action_contract, query_contract
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
            "/api/v1/app/finance",
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
        SettingField(
            "fiscal_year_start_month",
            "int",
            default=1,
            label="Fiscal year starts in month",
            description="1 for the calendar year; the year is named after the year it starts in",
        ),
        SettingField(
            "fee_basis_source",
            "choice",
            default="manual",
            label="Yearly expenses come from",
            choices=("manual", "recurring", "last_year", "budget"),
        ),
        SettingField(
            "fee_basis_extra",
            "float",
            default=0.0,
            label="Extra yearly costs (CHF)",
        ),
        SettingField(
            "fee_basis_manual",
            "float",
            default=None,
            label="Yearly expenses (CHF)",
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
                "finance.accounts.read",
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
        "accounts",
        "fiscal_years",
    ),
    provides=(
        query_contract(
            "finance.billing_period",
            "hubra.api.finance.contracts:billing_period",
            input="hubra.api.finance.contracts:PeriodIn",
            output="hubra.api.finance.contracts:Period",
            description="The club's billing year around a day",
        ),
        action_contract(
            "finance.invoice.set_status",
            "hubra.api.finance.contracts:set_invoice_status",
            input="hubra.api.finance.contracts:InvoiceStatusIn",
            output="hubra.api.finance.contracts:InvoiceStatus",
            perm="finance.invoices.update",
            description="Mark an invoice paid, or open again",
        ),
        action_contract(
            "finance.invoice.create",
            "hubra.api.finance.contracts:create_invoice",
            input="hubra.api.finance.contracts:InvoiceIn",
            output="hubra.api.finance.contracts:InvoiceOut",
            perm="finance.invoices.create",
            description="Invoice a member or an outside party",
        ),
        action_contract(
            "finance.invoice.delete",
            "hubra.api.finance.contracts:delete_invoice",
            input="hubra.api.finance.contracts:InvoiceRef",
            output="hubra.api.finance.contracts:InvoiceDeleted",
            perm="finance.invoices.delete",
            description="Withdraw an invoice, with its booking",
        ),
        action_contract(
            "finance.external_party.save",
            "hubra.api.finance.contracts:save_external_party",
            input="hubra.api.finance.contracts:ExternalPartyIn",
            output="hubra.api.finance.contracts:ExternalPartyOut",
            perm="finance.external_parties.create",
            description="Create an outside party, or keep one up to date",
        ),
    ),
)
