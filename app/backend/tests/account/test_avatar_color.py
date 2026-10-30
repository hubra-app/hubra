"""New accounts get a random avatar colour; existing accounts keep theirs."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import select

from hubra.core.avatar import AVATAR_COLORS

PASSWORD = "VeryStrongPass123!"


def _signup(client, email):
    resp = client.post(
        "/api/v1/auth/signup",
        json={"name": "New User", "email": email, "password": PASSWORD},
    )
    assert resp.status_code == 201, resp.get_json()


def _user(db, email):
    from hubra.core.models.user import User

    return db.session.scalar(select(User).where(User.email == email))


def test_signup_picks_a_colour_from_the_palette(client, db):
    with patch("hubra.core.avatar.random.choice", return_value="#1f9d57") as pick:
        _signup(client, "new@test.ch")
    pick.assert_called_with(AVATAR_COLORS)
    assert _user(db, "new@test.ch").avatar_color == "#1f9d57"


def test_new_accounts_do_not_all_share_one_colour(db):
    from hubra.core.models.user import User

    users = [
        User(email=f"u{i}@test.ch", first_name="U", last_name=str(i)) for i in range(40)
    ]
    for user in users:
        user.set_password(PASSWORD)
    db.session.add_all(users)
    db.session.commit()

    colours = {user.avatar_color for user in users}
    assert colours <= set(AVATAR_COLORS)
    assert len(colours) > 1


def test_an_explicit_colour_wins(db):
    from hubra.core.models.user import User

    user = User(
        email="set@test.ch", first_name="Set", last_name="User", avatar_color="#7441e0"
    )
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    assert user.avatar_color == "#7441e0"


def test_an_existing_account_keeps_its_colour(db):
    from hubra.core.models.user import User

    user = User(
        email="old@test.ch", first_name="Old", last_name="User", avatar_color="#6366f1"
    )
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()

    user.first_name = "Renamed"
    db.session.commit()
    db.session.expire_all()
    assert _user(db, "old@test.ch").avatar_color == "#6366f1"


def test_palette_colours_are_valid_hex():
    assert AVATAR_COLORS
    for colour in AVATAR_COLORS:
        assert len(colour) == 7 and colour.startswith("#")
        int(colour[1:], 16)
