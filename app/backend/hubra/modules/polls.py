"""Polls: member polls and votes."""

from hubra.core.modules import Blueprint, Module, NavItem, SettingField

module = Module(
    code="polls",
    name="Polls",
    description="Member polls and voting",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.polls.routes",
            "polls_bp",
            "/api/v1/polls",
        ),
    ),
    settings=(
        SettingField(
            "notify_members",
            "bool",
            default=True,
            label="Notify members about new polls",
            description="An in-app notification for every member when a poll is published",
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
