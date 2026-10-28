"""Posts: announcements with likes and comments."""

from vollbuild.core.modules import Blueprint, Module, NavItem

module = Module(
    code="posts",
    name="Posts",
    description="Club announcements and community posts",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "vollbuild.api.posts.routes",
            "posts_bp",
            "/api/v1/posts",
            v2=(("/api/v2/tenants/posts", "posts_bp_v2"),),
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
