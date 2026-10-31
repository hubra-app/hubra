"""Function service — CRUD, holder assignment, mail provisioning."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.function import Function, FunctionHolder


def _holder_count(value) -> int:
    """At least one holder; a value that is not a whole number is a 400."""
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", "maxHolders must be a whole number")


def _actor(actor_id: int | None):
    from hubra.core.models.member import Member

    return db.session.get(Member, actor_id) if actor_id is not None else None


def _granted_role(role_id):
    """The role a function is to give its holders; None clears it."""
    from hubra.core.models.role import Role

    if role_id in (None, ""):
        return None
    try:
        role = db.session.get(Role, int(role_id))
    except (TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", "grantsRoleId must be a role id")
    if role is None:
        raise_error(400, "VALIDATION_ERROR", f"Role {role_id} not found")
    if role.is_owner:
        # Owners are named one by one, with the last-owner rule.
        raise_error(400, "VALIDATION_ERROR", "A function cannot give the Owner role")
    return role


def _refresh_holders(fn: Function) -> None:
    from hubra.api.permissions import invalidate_member_permissions

    for holder in fn.holders:
        invalidate_member_permissions(holder.member_id)


class FunctionService:
    @staticmethod
    def list_all() -> list[Function]:
        from hubra.core.models.member import Member

        # Holders, their members and accounts in three queries, not three
        # per function.
        return list(
            db.session.scalars(
                select(Function)
                .order_by(Function.name)
                .options(
                    selectinload(Function.holders)
                    .selectinload(FunctionHolder.member)
                    .selectinload(Member.user)
                )
            ).all()
        )

    @staticmethod
    def get_by_id(function_id: int) -> Function:
        fn = db.session.get(Function, function_id)
        if fn is None:
            raise_error(404, "NOT_FOUND", f"Function {function_id} not found")
        return fn

    @staticmethod
    def create(
        name: str,
        description: str | None = None,
        max_holders: int = 1,
        grants_role_id=None,
        actor_id: int | None = None,
    ) -> Function:
        name = name.strip() if isinstance(name, str) else ""
        if not name:
            raise_error(400, "VALIDATION_ERROR", "Function name cannot be empty")
        max_holders = _holder_count(max_holders)

        existing = db.session.scalar(select(Function).where(Function.name == name))
        if existing is not None:
            raise_error(409, "CONFLICT", f"Function '{name}' already exists")

        role = _granted_role(grants_role_id)
        if role is not None:
            from hubra.api.permissions import check_grant

            check_grant(_actor(actor_id), given=[role])
        fn = Function(
            name=name,
            description=description,
            max_holders=max_holders,
            grants_tenant_role_id=role.id if role is not None else None,
        )
        db.session.add(fn)
        db.session.flush()

        from hubra.core.services.binding_engine import sync_for_source

        sync_for_source("function", str(fn.id))

        from hubra.core.services.managed_mail import auto_create_mma_for_function

        auto_create_mma_for_function(fn.id)

        return fn

    @staticmethod
    def update(function_id: int, actor_id: int | None = None, **fields) -> Function:
        fn = FunctionService.get_by_id(function_id)

        if "grants_role_id" in fields:
            role = _granted_role(fields["grants_role_id"])
            new_id = role.id if role is not None else None
            if new_id != fn.grants_tenant_role_id:
                from hubra.api.permissions import check_grant
                from hubra.core.models.role import Role

                old = (
                    db.session.get(Role, fn.grants_tenant_role_id)
                    if fn.grants_tenant_role_id
                    else None
                )
                # Linking a role gives it to every holder; unlinking takes it.
                check_grant(
                    _actor(actor_id),
                    given=[role] if role is not None else [],
                    taken=[old] if old is not None else [],
                )
                fn.grants_tenant_role_id = new_id
                _refresh_holders(fn)

        allowed = {"name", "description", "max_holders"}
        updates = {k: v for k, v in fields.items() if k in allowed}

        if "name" in updates:
            name = updates["name"].strip() if isinstance(updates["name"], str) else ""
            if not name:
                raise_error(400, "VALIDATION_ERROR", "Function name cannot be empty")
            if name != fn.name:
                existing = db.session.scalar(
                    select(Function).where(Function.name == name)
                )
                if existing is not None:
                    raise_error(409, "CONFLICT", f"Function '{name}' already exists")
            updates["name"] = name

        if "max_holders" in updates:
            updates["max_holders"] = _holder_count(updates["max_holders"])
            current_holders = len(fn.holders)
            if updates["max_holders"] < current_holders:
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    f"max_holders ({updates['max_holders']}) is less than current holders ({current_holders})",
                )

        for key, val in updates.items():
            setattr(fn, key, val)

        from hubra.core.services.binding_engine import sync_for_source

        sync_for_source("function", str(fn.id))
        return fn

    @staticmethod
    def delete(function_id: int, actor_id: int | None = None) -> None:
        from hubra.api.permissions import invalidate_member_permissions
        from hubra.core.services.managed_mail import remove_for_function

        fn = FunctionService.get_by_id(function_id)
        # The holders lose the role the function gives them.
        _check_role_change(fn, actor_id, give=False)
        holder_ids = [h.member_id for h in fn.holders]

        from hubra.core.services.binding_engine import (
            assert_source_deletable,
            assert_mail_address_owner_deletable,
            cascade_delete_disabled,
        )

        assert_source_deletable("function", str(function_id))
        assert_mail_address_owner_deletable("function", function_id)

        remove_for_function(function_id)
        db.session.delete(fn)

        cascade_delete_disabled("function", str(function_id))
        for member_id in holder_ids:
            invalidate_member_permissions(member_id)

    @staticmethod
    def assign_holder(
        function_id: int, member_id: int, actor_id: int | None = None
    ) -> FunctionHolder:
        from hubra.core.models.member import Member

        fn = FunctionService.get_by_id(function_id)
        # Under a row lock, so two assignments cannot both pass max_holders.
        db.session.refresh(fn, with_for_update=True)

        member = db.session.get(Member, member_id)
        if member is None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
        if member.archived_at is not None:
            raise_error(
                400, "VALIDATION_ERROR", "Cannot assign archived member to a function"
            )

        existing = db.session.scalar(
            select(FunctionHolder)
            .where(FunctionHolder.function_id == function_id)
            .where(FunctionHolder.member_id == member_id)
        )
        if existing is not None:
            raise_error(409, "CONFLICT", "Member already holds this function")

        current_count = len(fn.holders)
        if current_count >= fn.max_holders:
            raise_error(
                409,
                "CONFLICT",
                f"Function '{fn.name}' already has {current_count}/{fn.max_holders} holders",
            )

        _check_role_change(fn, actor_id, give=True)
        holder = FunctionHolder(function_id=function_id, member_id=member_id)
        db.session.add(holder)
        db.session.flush()
        from hubra.api.permissions import invalidate_member_permissions

        invalidate_member_permissions(member_id)

        _trigger_mail_sync(function_id)
        return holder

    @staticmethod
    def remove_holder(
        function_id: int, member_id: int, actor_id: int | None = None
    ) -> None:
        holder = db.session.scalar(
            select(FunctionHolder)
            .where(FunctionHolder.function_id == function_id)
            .where(FunctionHolder.member_id == member_id)
        )
        if holder is None:
            raise_error(404, "NOT_FOUND", "Holder not found for this function")

        _check_role_change(holder.function, actor_id, give=False)
        db.session.delete(holder)
        from hubra.api.permissions import invalidate_member_permissions

        invalidate_member_permissions(member_id)
        _trigger_mail_sync(function_id)

    @staticmethod
    def serialize(fn: Function) -> dict:
        holders = sorted(
            (fh for fh in fn.holders if fh.member is not None),
            key=lambda fh: fh.member_id,
        )
        return {
            "id": fn.id,
            "name": fn.name,
            "description": fn.description,
            "maxHolders": fn.max_holders,
            "grantsRoleId": fn.grants_tenant_role_id,
            "holders": [
                {
                    "memberId": fh.member_id,
                    "memberName": fh.member.name,
                    "assignedAt": fh.assigned_at.isoformat()
                    if fh.assigned_at
                    else None,
                }
                for fh in holders
            ],
        }


def _check_role_change(fn: Function, actor_id: int | None, *, give: bool) -> None:
    """A holder of a function that gives a role gets or loses that role, so
    the actor needs the right to give or take it, as on the member."""
    if fn.grants_tenant_role_id is None:
        return
    from hubra.api.permissions import check_grant
    from hubra.core.models.role import Role

    role = db.session.get(Role, fn.grants_tenant_role_id)
    if role is not None:
        check_grant(_actor(actor_id), given=[role] if give else [], taken=[] if give else [role])


def _trigger_mail_sync(function_id: int) -> None:
    """Dispatch reconcile_entity_forwarding task for a function.

    Only dispatches when at least one ManagedMailAddress exists for the
    function — avoids unnecessary Celery calls (and Redis connections
    in test environments) when no mail is configured.
    Falls back to inline sync when Celery is unavailable.
    """
    from hubra.core.models.managed_mail import ManagedMailAddress

    has_mma = db.session.scalar(
        select(ManagedMailAddress.id).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
        )
    )
    if has_mma is None:
        return

    try:
        from hubra.core.tasks.mail_tasks import reconcile_entity_forwarding_task

        reconcile_entity_forwarding_task.delay("function", function_id)
    except Exception:
        from hubra.core.services.mail_provisioning import (
            reconcile_entity_forwarding,
        )

        # A savepoint: a failure here must not undo the change that
        # triggered the sync, which the caller has not committed yet.
        try:
            with db.session.begin_nested():
                reconcile_entity_forwarding("function", function_id)
        except Exception:
            logging.getLogger(__name__).warning(
                "Inline mail sync failed for function %s", function_id, exc_info=True
            )
