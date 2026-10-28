"""Posts: announcements with likes and comments."""

from hubra.core.modules import Blueprint, Module, NavItem

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
    nav=(
        NavItem(
            "/app/operations/posts",
            "shell.nav.management",
            "layout-list",
            order=42,
            group="management",
        ),
    ),
    tables=("posts", "post_likes", "post_comments"),
)
