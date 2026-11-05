"""Webhooks: the club's own tools hear about changes (docs/webhooks.md)."""

from hubra.core.modules import Blueprint, Module

module = Module(
    code="webhooks",
    name="Webhooks",
    description="Signed messages to the club's own tools when members join or leave, invoices are paid and more",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.webhooks.routes",
            "webhooks_bp",
            "/api/v1/app/webhooks",
        ),
    ),
    tables=("webhooks", "webhook_deliveries"),
    tasks=("hubra.core.tasks.webhook_tasks",),
)
