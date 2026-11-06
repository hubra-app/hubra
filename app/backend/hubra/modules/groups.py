"""Groups: organisational groups and member-joinable interest groups."""

from hubra.core.contracts import action_contract, query_contract
from hubra.core.modules import Blueprint, Module, NavItem

_C = "hubra.api.groups.contracts"

module = Module(
    code="groups",
    name="Groups",
    description="Teams, committees and interest groups",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.groups.routes",
            "groups_bp",
            "/api/v1/app/groups",
        ),
    ),
    nav=(
        NavItem(
            "/app/groups",
            "shell.nav.groups",
            "box",
            order=20,
            perms=("groups.groups.read",),
            parent="/app/members",
        ),
    ),
    # What plugins use instead of the groups services (docs/contracts.md).
    provides=(
        query_contract(
            "groups.self_join.list",
            f"{_C}:joinable",
            input=f"{_C}:MemberRef",
            output=f"{_C}:JoinableGroup",
            description="Open groups a member may join or leave on their own",
        ),
        action_contract(
            "groups.self_join.set",
            f"{_C}:set_self_join",
            input=f"{_C}:SelfJoinIn",
            output=f"{_C}:SelfJoin",
            description="Join or leave an open group",
        ),
    ),
    tables=("groups", "group_memberships"),
)
