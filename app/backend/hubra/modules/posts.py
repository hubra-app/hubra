"""Posts: announcements with likes and comments."""

from hubra.core.modules import Blueprint, Module, NavItem, Schedule, SettingField
from hubra.core.contracts.search import search_contract

module = Module(
    code="posts",
    name="Posts",
    description="Club announcements and community posts",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.posts.routes",
            "posts_bp",
            "/api/v1/app/posts",
        ),
    ),
    settings=(
        SettingField(
            "notify_members",
            "bool",
            default=True,
            label="Notify members about new posts",
            description="An in-app notification for every member when a post is published",
        ),
        SettingField(
            "must_read_reminder_days",
            "int",
            default=7,
            label="Reminder for must-read posts (days)",
            description="Members who have not confirmed a must-read post this long after it went out get one reminder. 0: no reminder",
        ),
    ),
    nav=(
        NavItem(
            "/app/operations/posts",
            "shell.nav.posts",
            "news",
            section="activities",
            order=32,
        ),
    ),
    tables=(
        "posts",
        "post_likes",
        "post_comments",
        "post_reads",
        "comment_reports",
        "comment_mutes",
    ),
    tasks=("hubra.api.posts.tasks",),
    schedule=(
        # Scheduled posts go out within five minutes of their time.
        Schedule(
            "publish-scheduled-posts",
            "hubra.api.posts.tasks.publish_scheduled_posts_task",
            300,
        ),
        Schedule(
            "must-read-reminders",
            "hubra.api.posts.tasks.remind_unread_posts_task",
            3600,
        ),
    ),
    provides=(
        search_contract("posts", "hubra.api.search.sources:posts", perm="posts.posts.read"),
    ),
)
