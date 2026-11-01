"""Polls: member polls and votes."""

from hubra.core.modules import Blueprint, Module, NavItem, Schedule, SettingField

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
        SettingField(
            "reminder_hours",
            "int",
            default=24,
            label="Reminder before a poll closes (hours)",
            description="Members who have not voted get a reminder this long before the poll closes, in the app and by mail. 0: no reminders",
        ),
    ),
    nav=(
        NavItem(
            "/app/operations/polls",
            "shell.nav.polls",
            "chart-bar",
            section="activities",
            order=31,
        ),
    ),
    tables=("polls", "poll_options", "poll_votes", "poll_proxies"),
    tasks=("hubra.core.tasks.reminder_tasks",),
    schedule=(
        Schedule(
            "poll-reminders",
            "hubra.core.tasks.reminder_tasks.send_poll_reminders_task",
            900,
        ),
    ),
)
