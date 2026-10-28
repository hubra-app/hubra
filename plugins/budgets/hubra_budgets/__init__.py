"""Budgets: a plan per year and category, compared with booked transactions."""

from hubra.core.modules import Blueprint, Module

module = Module(
    code="finance.budgets",
    name="Budgets",
    description="Yearly budgets per category, with actuals from transactions",
    default_enabled=False,
    depends_on=("finance",),
    blueprints=(
        Blueprint(
            "hubra_budgets.routes",
            "budgets_bp",
            "/api/v1/budgets",
        ),
    ),
    tables=("budgets", "budget_lines"),
)
