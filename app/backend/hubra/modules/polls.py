"""Polls: member polls and votes."""

from hubra.core.contracts import action_contract, query_contract
from hubra.core.modules import Blueprint, Module, NavItem, Schedule, SettingField

_C = "hubra.api.polls.contracts"

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
            "/api/v1/app/polls",
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
    # What plugins use instead of the polls services (docs/contracts.md).
    provides=(
        query_contract(
            "polls.poll.get",
            f"{_C}:get_poll",
            input=f"{_C}:PollRef",
            output=f"{_C}:PollInfo",
            perm="polls.polls.read",
            description="Whether a poll is closed, and who still has to vote",
        ),
        action_contract(
            "polls.poll.create",
            f"{_C}:create_poll",
            input=f"{_C}:PollCreateIn",
            output=f"{_C}:PollCreated",
            perm="polls.polls.create",
            description="Create a poll",
        ),
        action_contract(
            "polls.poll.vote",
            f"{_C}:vote",
            input=f"{_C}:VoteIn",
            output=f"{_C}:Vote",
            perm="polls.polls.vote",
            description="Cast or change a vote, also as a proxy",
        ),
        query_contract(
            "polls.proxies.held",
            f"{_C}:proxies_held",
            input=f"{_C}:HeldIn",
            output=f"{_C}:Proxy",
            perm="polls.polls.read",
            description="The proxies a member holds for a poll",
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
