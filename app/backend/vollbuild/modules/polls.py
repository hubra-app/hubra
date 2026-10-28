"""Polls: member polls and votes."""

from vollbuild.core.modules import Blueprint, Module, NavItem

module = Module(
    code="polls",
    name="Polls",
    description="Member polls and voting",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "vollbuild.api.polls.routes",
            "polls_bp",
            "/api/v1/polls",
            v2=(("/api/v2/tenants/polls", "polls_bp_v2"),),
        ),
    ),
    nav=(
        NavItem(
            "/app/operations/polls",
            "shell.nav.management",
            "layout-list",
            order=41,
            group="management",
        ),
    ),
    tables=("polls", "poll_options", "poll_votes", "poll_proxies"),
)
