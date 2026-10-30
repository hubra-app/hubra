"""Posts: announcements with likes and comments."""

from hubra.core.modules import Blueprint, Module, NavItem, SettingField

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
            "/api/v1/posts",
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
    tables=("posts", "post_likes", "post_comments"),
)
