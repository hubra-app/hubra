"""The shared mail server (WildDuck) as the platform sees it.

WildDuck is one server for every club.  A mailbox or alias there is managed
when *any* club has a ManagedMailAddress for it, so the live list and every
orphan check have to look at all clubs, never at one club alone.
"""

from __future__ import annotations

from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.tenant import Tenant
from hubra.core.services.wildduck import WildDuckClient, WildDuckError, try_get_client
from hubra.core.tenant.context import in_club


def _client() -> WildDuckClient:
    wd = try_get_client()
    if wd is None:
        raise_error(
            503, "SERVICE_UNAVAILABLE", "Mail server integration is not configured"
        )
    return wd  # type: ignore[return-value]


def _mail_clubs() -> list[Tenant]:
    from hubra.core.modules.state import is_enabled

    tenants = db.session.scalars(select(Tenant).where(Tenant.status == "active")).all()
    return [t for t in tenants if is_enabled("mail", tenant_id=t.id)]


def _owner_names(mmas) -> dict[tuple[str, int], str]:
    """``{(owner_type, owner_id): name}`` for the owners of *mmas*."""
    from hubra.core.models.function import Function
    from hubra.core.models.group import Group
    from hubra.core.models.member import Member

    names: dict[tuple[str, int], str] = {}
    for owner_type, model in (
        ("member", Member),
        ("group", Group),
        ("function", Function),
    ):
        ids = {m.owner_id for m in mmas if m.owner_type == owner_type and m.owner_id}
        if ids:
            for row in db.session.scalars(select(model).where(model.id.in_(ids))):
                names[(owner_type, row.id)] = row.name
    return names


def _club_entries() -> dict[str, dict]:
    """The current club's managed addresses, keyed by WildDuck id and address."""
    from hubra.core.models.managed_mail import ManagedMailAddress

    mmas = db.session.scalars(select(ManagedMailAddress)).all()
    names = _owner_names(mmas)
    index: dict[str, dict] = {}
    for mma in mmas:
        info = {
            "mmaId": mma.id,
            "kind": mma.kind or mma.owner_type or "system",
            "linkedId": mma.owner_id,
            "ownerName": names.get((mma.owner_type, mma.owner_id)),
        }
        for wd_id in (mma.wildduck_id, mma.wildduck_user_id):
            if wd_id:
                index[wd_id] = info
        if mma.address:
            index.setdefault(f"addr:{mma.address}", info)
    return index


def managed_index() -> dict[str, dict]:
    """Every club's managed addresses, keyed by WildDuck id and ``addr:<address>``.

    Each value names the club it belongs to.  Pending ORM changes are not
    flushed while another club's schema is active.
    """
    tenants = _mail_clubs()
    index: dict[str, dict] = {}
    with db.session.no_autoflush:
        if not tenants:
            for key, info in _club_entries().items():
                index.setdefault(key, {**info, "club": None})
            return index
        for tenant in tenants:
            club = {"slug": tenant.slug, "name": tenant.name}
            with in_club(tenant):
                for key, info in _club_entries().items():
                    index.setdefault(key, {**info, "club": club})
    return index


def live() -> list[dict]:
    """Every WildDuck mailbox and alias, with the club that manages it (or none)."""
    wd = _client()
    try:
        users = wd.list_users(limit=250).get("results", [])
    except WildDuckError as exc:
        raise_error(502, "INTERNAL_ERROR", f"WildDuck: {exc.message}")
    try:
        aliases = wd.list_addresses().get("results", [])
    except WildDuckError:
        aliases = []

    index = managed_index()
    result: list[dict] = []

    def entry(kind: str, raw: dict, managed: dict | None, quota: dict | None):
        managed = managed or {}
        return {
            "id": raw["id"],
            "type": kind,
            "address": raw.get("address", ""),
            "name": raw.get("name", ""),
            "disabled": raw.get("disabled", False),
            "targets": raw.get("targets") or [],
            "quotaUsed": quota.get("used", 0) if quota is not None else None,
            "quotaTotal": quota.get("allowed", 0) if quota is not None else None,
            "managed": bool(managed),
            "club": managed.get("club"),
            "mmaId": managed.get("mmaId"),
            "kind": managed.get("kind"),
            "linkedId": managed.get("linkedId"),
            "ownerName": managed.get("ownerName"),
        }

    for u in users:
        result.append(entry("mailbox", u, index.get(u["id"]), u.get("quota") or {}))
    for a in aliases:
        if a.get("user"):
            continue
        managed = index.get(a["id"]) or index.get(f"addr:{a.get('address', '')}")
        result.append(entry("alias", a, managed, None))
    return result


def delete_orphan(entry_type: str, entry_id: str) -> str:
    """Delete a WildDuck entry no club manages; returns its address for the audit.

    Raises 409 when any club manages it.
    """
    managed = managed_index().get(entry_id)
    if managed is not None:
        club = (managed.get("club") or {}).get("name") or "a club"
        raise_error(
            409,
            "CONFLICT",
            f"{club} manages this entry; remove it in that club's mail settings",
        )

    wd = _client()
    try:
        if entry_type == "mailbox":
            label = wd.get_user(entry_id).get("address", entry_id)
            wd.delete_user(entry_id)
        else:
            label = entry_id
            wd.safe_delete_forwarding_alias(entry_id)
    except WildDuckError as exc:
        if exc.status == 404:
            raise_error(404, "NOT_FOUND", f"WildDuck {entry_type} {entry_id} not found")
        raise
    return label
