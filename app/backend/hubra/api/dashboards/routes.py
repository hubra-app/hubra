"""Own dashboards (docs/dashboards.md).

``/api/v1/app/dashboards``. Every member puts dashboards together from
widgets. A dashboard is private to its owner until it is shared, which
needs ``dashboards.dashboards.share``: with the whole club, or with chosen
groups (their members see it). Each viewer sees only the widgets their own
rights allow (the widgets load their data through the usual routes).

* ``GET  /``               the member's own dashboards and the shared ones
* ``POST /``               a new private dashboard
* ``GET  /<id>``           one (own or shared)
* ``PATCH /<id>``          name and widgets (the owner, or an admin)
* ``PUT  /<id>/sharing``   ``{"shared": bool, "groupIds": [int]}`` (the owner
                           with the right to share; an admin may also stop
                           sharing any). groupIds empty or left out: the club
* ``DELETE /<id>``         remove it (the owner, or an admin)

The start pages (Dashboard › Verein and › Persönlich) are widget lists too.
Until someone changes one, the app shows its built-in layout (``null``):

* ``GET  /home``           ``{"club": {...}, "me": {...}}``
* ``PUT  /home/club``      ``{"widgets": [...]}``, needs ``dashboards.home.update``
* ``DELETE /home/club``    back to the built-in layout (same right)
* ``PUT  /home/me``        the member's own start page
* ``DELETE /home/me``      back to the built-in layout

Widgets that modules and plugins offer as contracts (docs/contracts.md):

* ``GET  /widgets``              the ones this member may add here
* ``POST /widgets/<name>/data``  ``{"config": {...}}``: what one shows
"""

from __future__ import annotations

import json
import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func, or_, select

from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import error_message, api_error
from hubra.core.extensions import db
from hubra.core.models.dashboard import Dashboard
from hubra.core.models.group import Group, GroupMembership
from hubra.core.permissions import (
    member_has_permission,
    member_is_admin,
    permission_required,
)
from hubra.core.utils import log_audit

dashboards_bp = Blueprint("dashboards_bp", __name__)

MAX_DASHBOARDS = 20  # per member
MAX_WIDGETS = 24
MAX_CONFIG = 4000  # characters of a widget's config as JSON
SIZES = ("s", "m", "l")
COLS = 12  # the grid's columns; a widget spans 2 to 12
MAX_ROWS = 24  # a widget's set height in rows; none: as tall as its content
SHARE_PERM = "dashboards.dashboards.share"
HOME_PERM = "dashboards.home.update"
# Built-in types are camelCase (polls.voteNeeded, stat.openInvoices).
_TYPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _dump(d: Dashboard, member) -> dict:
    owner = d.owner
    return {
        "id": d.id,
        "name": d.name,
        "shared": d.shared,
        "groups": _groups_of(d),
        "widgets": list(d.widgets or []),
        "owner": {
            "id": d.owner_id,
            "name": owner.name if owner else None,
        },
        "mine": d.owner_id == member.id,
        "canEdit": _can_edit(d, member),
        "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
    }


def _can_edit(d: Dashboard, member) -> bool:
    return d.owner_id == member.id or member_is_admin(member)


def _my_groups(member) -> set[int]:
    return set(
        db.session.scalars(
            select(GroupMembership.group_id).where(GroupMembership.member_id == member.id)
        )
    )


def _groups_of(d: Dashboard) -> list[dict]:
    """The groups a dashboard is shared with, [] for the whole club."""
    ids = [i for i in (d.group_ids or []) if isinstance(i, int)]
    if not ids:
        return []
    rows = db.session.execute(
        select(Group.id, Group.name).where(Group.id.in_(ids)).order_by(Group.name)
    ).all()
    return [{"id": gid, "name": name} for gid, name in rows]


def _shared_with(d: Dashboard, member, mine: set[int] | None = None) -> bool:
    """Whether *member* sees *d* because it is shared (club or their group)."""
    if not d.shared:
        return False
    ids = d.group_ids or []
    if not ids:
        return True
    return bool(set(ids) & (_my_groups(member) if mine is None else mine))


def _can_see(d: Dashboard, member) -> bool:
    return _can_edit(d, member) or _shared_with(d, member)


def _group_ids(value):
    """Validated group ids for sharing, or an error text."""
    if value is None:
        return [], None
    if not isinstance(value, list) or len(value) > 50:
        return None, "groupIds must be a list of at most 50 group ids"
    ids = []
    for v in value:
        if isinstance(v, bool) or not isinstance(v, int):
            return None, "groupIds must be a list of group ids"
        if v not in ids:
            ids.append(v)
    if ids:
        found = set(db.session.scalars(select(Group.id).where(Group.id.in_(ids))))
        if found != set(ids):
            return None, "groupIds holds a group that does not exist"
    return ids, None


def _name(value) -> str | None:
    name = str(value or "").strip()[:100]
    return name or None


def _widgets(value):
    """Validated widgets, or an error text."""
    if not isinstance(value, list):
        return None, "widgets must be a list"
    if len(value) > MAX_WIDGETS:
        return None, f"At most {MAX_WIDGETS} widgets"
    out, seen = [], set()
    for i, w in enumerate(value):
        if not isinstance(w, dict):
            return None, f"widgets[{i}] must be an object"
        wid, wtype = w.get("id"), w.get("type")
        if not isinstance(wid, str) or not _ID.match(wid) or wid in seen:
            return None, f"widgets[{i}].id must be a unique short name"
        if not isinstance(wtype, str) or not _TYPE.match(wtype):
            return None, f"widgets[{i}].type is not valid"
        size = w.get("size", "m")
        if size not in SIZES:
            return None, f"widgets[{i}].size is one of {', '.join(SIZES)}"
        grid = {}
        for key, low, high in (("w", 2, COLS), ("h", 1, MAX_ROWS)):
            n = w.get(key)
            if n is None:
                continue
            if isinstance(n, bool) or not isinstance(n, int) or not low <= n <= high:
                return None, f"widgets[{i}].{key} is a whole number from {low} to {high}"
            grid[key] = n
        if "w" in grid and "size" not in w:
            size = "s" if grid["w"] <= 4 else "m" if grid["w"] <= 8 else "l"
        config = w.get("config") or {}
        if not isinstance(config, dict):
            return None, f"widgets[{i}].config must be an object"
        if len(json.dumps(config, ensure_ascii=False)) > MAX_CONFIG:
            return None, f"widgets[{i}].config is too large"
        seen.add(wid)
        out.append({"id": wid, "type": wtype, "size": size, **grid, "config": config})
    return out, None


def _get(dashboard_id: int, member):
    d = db.session.get(Dashboard, dashboard_id)
    if d is None or d.home is not None or not _can_see(d, member):
        return None
    return d


def _audit(action: str, d: Dashboard, member) -> None:
    log_audit(
        actor_id=member.id,
        action=action,
        target_type="Dashboard",
        target_id=d.id,
        target_label=d.name,
    )


@dashboards_bp.get("/")
@jwt_required()
def list_dashboards():
    member = get_current_member()
    rows = db.session.scalars(
        select(Dashboard)
        .where(Dashboard.home.is_(None))
        .where(or_(Dashboard.owner_id == member.id, Dashboard.shared.is_(True)))
        .order_by(Dashboard.name, Dashboard.id)
    ).all()
    mine = _my_groups(member)
    admin = member_is_admin(member)
    # Shared with groups: only their members, the owner and admins see it.
    rows = [
        d for d in rows if d.owner_id == member.id or admin or _shared_with(d, member, mine)
    ]
    return jsonify(
        {
            "items": [_dump(d, member) for d in rows],
            "canShare": member_has_permission(member, SHARE_PERM),
            "max": MAX_DASHBOARDS,
        }
    ), 200


@dashboards_bp.post("/")
@jwt_required()
def create_dashboard():
    member = get_current_member()
    count = db.session.scalar(
        select(func.count(Dashboard.id)).where(
            Dashboard.owner_id == member.id, Dashboard.home.is_(None)
        )
    )
    if (count or 0) >= MAX_DASHBOARDS:
        return api_error(
            "LIMIT_REACHED", f"At most {MAX_DASHBOARDS} dashboards each", 409
        )
    data = _body()
    name = _name(data.get("name"))
    if name is None:
        return api_error("VALIDATION_ERROR", "A name is required", 400)
    widgets, error = _widgets(data.get("widgets", []))
    if error:
        return api_error("VALIDATION_ERROR", error, 400)
    d = Dashboard(name=name, owner_id=member.id, shared=False, widgets=widgets)
    db.session.add(d)
    db.session.commit()
    return jsonify(_dump(d, member)), 201


# ── Start pages ────────────────────────────────────────────────────────────


def _home_row(kind: str, member):
    query = select(Dashboard).where(Dashboard.home == kind)
    if kind == "me":
        query = query.where(Dashboard.owner_id == member.id)
    return db.session.scalars(query.order_by(Dashboard.id).limit(1)).first()


def _home_dump(row) -> dict:
    return {
        "widgets": list(row.widgets or []) if row else None,
        "updatedAt": row.updated_at.isoformat() if row and row.updated_at else None,
    }


def _save_home(kind: str, member):
    widgets, error = _widgets(_body().get("widgets"))
    if error:
        return api_error("VALIDATION_ERROR", error, 400)
    row = _home_row(kind, member)
    if row is None:
        row = Dashboard(
            name="Verein" if kind == "club" else "Persönlich",
            owner_id=member.id,
            shared=kind == "club",
            home=kind,
        )
        db.session.add(row)
    row.widgets = widgets
    if kind == "club":
        # The last one to change it; the row goes if they are deleted, and
        # the club falls back to the built-in layout.
        row.owner_id = member.id
        db.session.flush()
        _audit("update_club_home", row, member)
    db.session.commit()
    return jsonify(_home_dump(row)), 200


def _reset_home(kind: str, member):
    row = _home_row(kind, member)
    if row is not None:
        if kind == "club":
            _audit("reset_club_home", row, member)
        db.session.delete(row)
        db.session.commit()
    return jsonify(_home_dump(None)), 200


@dashboards_bp.get("/home")
@jwt_required()
def get_home():
    member = get_current_member()
    return jsonify(
        {
            "club": {
                **_home_dump(_home_row("club", member)),
                "canEdit": member_has_permission(member, HOME_PERM),
            },
            "me": {**_home_dump(_home_row("me", member)), "canEdit": True},
        }
    ), 200


@dashboards_bp.put("/home/club")
@permission_required("home", "update", "Change the club's start page")
def save_club_home():
    return _save_home("club", get_current_member())


@dashboards_bp.delete("/home/club")
@permission_required("home", "update", "Change the club's start page")
def reset_club_home():
    return _reset_home("club", get_current_member())


@dashboards_bp.put("/home/me")
@jwt_required()
def save_my_home():
    return _save_home("me", get_current_member())


@dashboards_bp.delete("/home/me")
@jwt_required()
def reset_my_home():
    return _reset_home("me", get_current_member())


@dashboards_bp.get("/<int:dashboard_id>")
@jwt_required()
def get_dashboard(dashboard_id: int):
    member = get_current_member()
    d = _get(dashboard_id, member)
    if d is None:
        return api_error("NOT_FOUND", "No such dashboard", 404)
    return jsonify(_dump(d, member)), 200


@dashboards_bp.patch("/<int:dashboard_id>")
@jwt_required()
def update_dashboard(dashboard_id: int):
    member = get_current_member()
    d = _get(dashboard_id, member)
    if d is None:
        return api_error("NOT_FOUND", "No such dashboard", 404)
    if not _can_edit(d, member):
        return api_error("FORBIDDEN", "Only its owner changes a dashboard", 403)
    data = _body()
    if "name" in data:
        name = _name(data["name"])
        if name is None:
            return api_error("VALIDATION_ERROR", "A name is required", 400)
        d.name = name
    if "widgets" in data:
        widgets, error = _widgets(data["widgets"])
        if error:
            return api_error("VALIDATION_ERROR", error, 400)
        d.widgets = widgets
    if d.shared:
        _audit("update_dashboard", d, member)
    db.session.commit()
    return jsonify(_dump(d, member)), 200


@dashboards_bp.put("/<int:dashboard_id>/sharing")
@permission_required("dashboards", "share", "Share dashboards with the club")
def share_dashboard(dashboard_id: int):
    member = get_current_member()
    d = _get(dashboard_id, member)
    if d is None:
        return api_error("NOT_FOUND", "No such dashboard", 404)
    body = _body()
    shared = body.get("shared")
    if not isinstance(shared, bool):
        return api_error("VALIDATION_ERROR", "shared must be true or false", 400)
    group_ids, error = _group_ids(body.get("groupIds") if shared else None)
    if error:
        return api_error("VALIDATION_ERROR", error, 400)
    if d.owner_id != member.id and not (member_is_admin(member) and not shared):
        return api_error("FORBIDDEN", "Only its owner shares a dashboard", 403)
    d.shared = shared
    d.group_ids = group_ids or None
    _audit("share_dashboard" if shared else "unshare_dashboard", d, member)
    db.session.commit()
    return jsonify(_dump(d, member)), 200


@dashboards_bp.delete("/<int:dashboard_id>")
@jwt_required()
def delete_dashboard(dashboard_id: int):
    member = get_current_member()
    d = _get(dashboard_id, member)
    if d is None:
        return api_error("NOT_FOUND", "No such dashboard", 404)
    if not _can_edit(d, member):
        return api_error("FORBIDDEN", "Only its owner deletes a dashboard", 403)
    if d.shared:
        _audit("delete_dashboard", d, member)
    db.session.delete(d)
    db.session.commit()
    return "", 204


# ── Widgets offered as contracts ────────────────────────────────────────────


def _widget(offer) -> dict:
    c = offer.contract
    return {
        "name": c.name,
        "type": f"w:{c.name}",
        "module": offer.module_code,
        "plugin": offer.plugin,
        "description": c.description,
        "perm": c.perm,
        **offer.widget_dict(),
    }


@dashboards_bp.get("/widgets")
@jwt_required()
def list_widgets():
    from hubra.core import contracts

    member = get_current_member()
    return jsonify({"items": [_widget(o) for o in contracts.widgets(actor=member)]}), 200


@dashboards_bp.post("/widgets/<name>/data")
@jwt_required()
def widget_data(name: str):
    from hubra.core import contracts

    member = get_current_member()
    config = _body().get("config")
    try:
        data = contracts.widget_data(name, config, actor=member)
    except contracts.ActionUnavailable:
        return api_error("NOT_FOUND", "This widget isn't available here", 404)
    except contracts.ActionForbidden:
        return api_error("FORBIDDEN", "You may not see this widget", 403)
    except contracts.Refused as exc:
        return api_error(exc.code, error_message(exc), 409)
    except (contracts.ActionFailed, contracts.ContractError):
        return api_error("WIDGET_FAILED", "This widget couldn't load its data", 502)
    return jsonify({"data": data}), 200
