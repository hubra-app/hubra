"""Finance: QR-bill invoices, reminders, fees and external parties.

The books (transactions, categories, the overview, recurring bookings, the
monthly statement and the annual accounts) are the Finances plugin, module
``finance.books``. Its tables stay listed here: invoices point at their
booking, so they live in every club schema either way.
"""

from hubra.core.contracts import action_contract, query_contract, widget_contract
from hubra.core.modules import Blueprint, Module, NavItem, Schedule, SettingField
from hubra.core.contracts.search import search_contract

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
    # Finanzen › Einstellungen shows these with the fee schedule and plugin cards.
    settings_page="/app/finance/settings",
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
            "collect_items",
            "choice",
            default="off",
            label="Bill small items together",
            description="Drinks, booking fees and other open items go on one invoice per member each month or quarter; off: each on its own invoice",
            choices=("off", "monthly", "quarterly"),
        ),
        SettingField(
            "collect_min_amount",
            "float",
            default=0.0,
            label="Smallest collected invoice (CHF)",
            description="Below it the items wait for the next time",
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
        "open_items",
        "transaction_categories",
        "external_parties",
        "invoice_reminder_history",
        "qrr_references",
        "recurring_transactions",
        "accounts",
        "fiscal_years",
    ),
    tasks=("hubra.api.finance.tasks",),
    schedule=(
        # Collected invoices go out on the first of a month or quarter.
        Schedule(
            "collect-open-items",
            "hubra.api.finance.tasks.collect_open_items_task",
            86400,
        ),
    ),
    provides=(
        search_contract("finance", "hubra.api.search.sources:invoices", perm="finance.invoices.read"),
        query_contract(
            "finance.billing_period",
            "hubra.api.finance.contracts:billing_period",
            input="hubra.api.finance.contracts:PeriodIn",
            output="hubra.api.finance.contracts:Period",
            description="The club's billing year around a day",
        ),
        action_contract(
            "finance.open_item.add",
            "hubra.api.finance.contracts:add_open_item",
            input="hubra.api.finance.contracts:OpenItemIn",
            output="hubra.api.finance.contracts:OpenItemOut",
            perm="finance.invoices.create",
            description="Something a member owes, for their next (collected) invoice",
        ),
        action_contract(
            "finance.open_item.remove",
            "hubra.api.finance.contracts:remove_open_item",
            input="hubra.api.finance.contracts:OpenItemRef",
            output="hubra.api.finance.contracts:OpenItemRemoved",
            perm="finance.invoices.create",
            description="Take an open item back before it is billed",
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
            "finance.transaction.create",
            "hubra.api.finance.contracts:create_transaction",
            input="hubra.api.finance.contracts:TransactionIn",
            output="hubra.api.finance.contracts:TransactionOut",
            perm="finance.transactions.create",
            description="Put one booking in the books",
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
        # Dashboard widgets (hubra/api/finance/widgets.py).
        widget_contract(
            "finance.invoices.ageing",
            "hubra.api.finance.widgets:ageing",
            label="dashboards.w.invoiceAgeing",
            description="dashboards.d.invoiceAgeing",
            size="m",
            view="list",
            perm="finance.invoices.read",
        ),
        widget_contract(
            "finance.invoices.expected",
            "hubra.api.finance.widgets:expected",
            label="dashboards.w.expectedIncome",
            description="dashboards.d.expectedIncome",
            size="s",
            view="stat",
            perm="finance.invoices.read",
        ),
    ),
)
