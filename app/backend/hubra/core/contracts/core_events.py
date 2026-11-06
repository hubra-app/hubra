"""Hubra's own events as contracts: name, version and payload.

The payloads are ids and plain values, so an event can travel to a worker
(and, later, through a message broker). Hubra may add fields to a payload
without a new version; handlers ignore fields they don't know.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from . import base


class _Payload(BaseModel):
    # Tolerant: a field added later doesn't break an older emitter's check.
    model_config = ConfigDict(extra="allow")


class InvoiceOverdue(_Payload):
    member_id: int | None = None
    invoice_id: int


class InvoicePaid(_Payload):
    member_id: int | None = None
    invoice_id: int


class InvoiceCreated(_Payload):
    invoice_id: int
    category_id: int | None = None


class InvoiceUpdated(_Payload):
    invoice_id: int
    was_paid: bool = False
    changed: list[str] = []


class InvoiceDeleted(_Payload):
    invoice_id: int
    transaction_id: int | None = None


class EventRef(_Payload):
    event_id: int


class EventChanged(_Payload):
    event_id: int
    deleted: bool = False


class PostRef(_Payload):
    post_id: int


class PollRef(_Payload):
    poll_id: int


class GroupMembershipChanged(_Payload):
    group_id: int
    member_id: int
    action: Literal["joined", "left"]


class AccountLink(_Payload):
    member_id: int
    user_id: int | None = None
    provider: str
    external_id: str | None = None


class MemberRef(_Payload):
    member_id: int


CORE_EVENTS: tuple[base.Contract, ...] = (
    base.event_contract(
        "invoice.overdue", InvoiceOverdue, description="An invoice is past due"
    ),
    base.event_contract("invoice.paid", InvoicePaid, description="An invoice was paid"),
    base.event_contract(
        "invoice.created", InvoiceCreated, description="An invoice was created"
    ),
    base.event_contract(
        "invoice.updated", InvoiceUpdated, description="An invoice was changed"
    ),
    base.event_contract(
        "invoice.deleted", InvoiceDeleted, description="An invoice was deleted"
    ),
    base.event_contract(
        "event.published", EventRef, description="An event was published"
    ),
    base.event_contract(
        "event.changed", EventChanged, description="An event was changed or deleted"
    ),
    base.event_contract(
        "event.signups_changed", EventRef, description="Sign-ups of an event changed"
    ),
    base.event_contract(
        "event.reminder", EventRef, description="An event's reminder is due"
    ),
    base.event_contract("post.published", PostRef, description="A post was published"),
    base.event_contract("poll.published", PollRef, description="A poll was published"),
    base.event_contract("poll.closing", PollRef, description="A poll closes soon"),
    base.event_contract(
        "poll.closed", PollRef, description="An organiser closed a poll"
    ),
    base.event_contract(
        "group.membership_changed",
        GroupMembershipChanged,
        description="Someone joined or left a group",
    ),
    base.event_contract(
        "account.linked", AccountLink, description="An outside account was linked"
    ),
    base.event_contract(
        "account.unlinked", AccountLink, description="An outside account was unlinked"
    ),
    base.event_contract(
        "member.joined", MemberRef, description="A member joined the club"
    ),
    base.event_contract("member.left", MemberRef, description="A member left the club"),
)
