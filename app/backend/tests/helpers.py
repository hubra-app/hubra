"""Small helpers shared by test modules."""

from datetime import date
from unittest.mock import patch

from hubra.api.settings.services import SettingService


def patch_mail_domain(domain: str):
    """Patch SettingService.get so only ``mail.domain`` returns *domain*."""
    real_get = SettingService.get

    def fake_get(key, default=None):
        return domain if key == "mail.domain" else real_get(key, default)

    return patch("hubra.api.settings.services.SettingService.get", side_effect=fake_get)


def set_modules(enabled: bool = True, *codes: str) -> None:
    """Switch modules on or off for installs without a tenant.

    With no *codes*, applies to every registered module.  Writes the
    catalog rows directly, so dependency checks are skipped on purpose.
    """
    from hubra.core.extensions import db
    from hubra.core.models.feature import Feature
    from hubra.core.modules import registry
    from hubra.core.modules.state import invalidate

    registry.load()
    for code in codes or [m.code for m in registry.all()]:
        row = db.session.get(Feature, code)
        if row is None:
            db.session.add(Feature(code=code, name=code, default_enabled=enabled))
        else:
            row.default_enabled = enabled
    db.session.commit()
    invalidate()


_ACCOUNT_FIELDS = (
    "phone",
    "mobile",
    "birthday",
    "address_street",
    "address_house_no",
    "address_postal_code",
    "address_city",
    "address_country",
    "emergency_contact",
)
_MEMBER_FIELDS = ("tool_hours", "joined", "membership_until", "custom_fields")


def add_member(client, auth_headers, **fields):
    """A person with their own account who accepted the club's invite.

    Clubs only invite (``POST /members`` answers 202), so tests that need a
    member make the account and accept for it. Takes the old create payload
    (email, names, account and member fields) and returns the club's
    ``GET /members/<id>`` response for the new member. An email that is
    already a member gives that member's 409 like the invite would.
    """
    from flask import json
    from sqlalchemy import func, select

    from hubra.api.members.services import MembersService
    from hubra.core.extensions import db
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    email = fields.get("email", "member@test.ch").lower()
    user = db.session.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        user = User(
            email=email,
            first_name=fields.get("first_name", "Test"),
            last_name=fields.get("last_name", "Member"),
        )
        user.set_password("Member-Pass-123!")
        for name in _ACCOUNT_FIELDS:
            if fields.get(name) is not None:
                value = fields[name]
                if name == "birthday" and isinstance(value, str):
                    value = date.fromisoformat(value)
                setattr(user, name, value)
        db.session.add(user)
        db.session.flush()
    elif db.session.scalar(
        select(Member.id).where(Member.user_id == user.id, Member.archived_at.is_(None))
    ):
        resp = client.post(
            "/api/v1/members/", json={"email": email}, headers=auth_headers
        )
        assert resp.status_code == 409, resp.get_data(as_text=True)
        return resp
    member = MembersService.add_account(
        user,
        {
            k: fields[k]
            for k in ("tier_id", "group_ids", "status", "membership_type", "notes")
            if k in fields
        },
    )
    for name in _MEMBER_FIELDS:
        if name in fields:
            value = fields[name]
            if name in ("joined", "membership_until") and isinstance(value, str):
                value = date.fromisoformat(value)
            setattr(member, name, value)
    db.session.commit()
    resp = client.get(f"/api/v1/members/{member.id}", headers=auth_headers)
    assert resp.status_code == 200, json.dumps(resp.get_json())
    return resp
