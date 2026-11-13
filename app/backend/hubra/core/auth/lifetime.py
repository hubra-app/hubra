"""How long a sign-in lasts.

"Keep me signed in" ticked: ``REFRESH_TOKEN_DAYS`` (default 30 days).
Not ticked: ``SHORT_SESSION_HOURS`` (default 24 hours).

Both count from the sign-in itself (the ``signed_in_at`` claim), not from
the last refresh.  Refresh-token rotation used to start a fresh 30 days on
every refresh, so a browser that opened Hubra once a month stayed signed in
for good.  Club switches, rotations and "end other sessions" keep the claim,
so none of them extends the sign-in.
"""

from __future__ import annotations

import time
from datetime import timedelta

from flask import current_app
from flask_jwt_extended import create_refresh_token, set_refresh_cookies

SIGNED_IN_AT = "signed_in_at"
KEEP = "keep"


def lifetime(keep: bool | None) -> timedelta:
    """The whole lifetime of a sign-in with or without "keep me signed in"."""
    if keep is False:
        return timedelta(hours=current_app.config["SHORT_SESSION_HOURS"])
    return current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]


def start_claims(keep: bool) -> dict:
    """The claims a new sign-in carries: its choice and its start."""
    return {KEEP: keep, SIGNED_IN_AT: int(time.time())}


def carry(claims: dict, into: dict) -> dict:
    """Copy the sign-in's choice and start from *claims* into *into*.

    A token from before ``signed_in_at`` existed starts its clock now: it
    gets one more full lifetime, then has to sign in again.
    """
    if claims.get(KEEP) is not None:
        into[KEEP] = claims[KEEP]
    into[SIGNED_IN_AT] = int(claims.get(SIGNED_IN_AT) or time.time())
    return into


def seconds_left(claims: dict) -> int:
    """Seconds until the sign-in behind *claims* ends (0 when it has)."""
    total = int(lifetime(claims.get(KEEP)).total_seconds())
    start = claims.get(SIGNED_IN_AT)
    if start is None:
        return total
    return max(0, int(start) + total - int(time.time()))


def set_refresh(response, identity: str, claims: dict) -> None:
    """A refresh token and cookie that end when the sign-in does.

    *claims* must already hold ``signed_in_at`` (see ``start_claims`` and
    ``carry``).  Callers check ``seconds_left`` first where it can be 0.
    """
    left = max(60, seconds_left(claims))
    set_refresh_cookies(
        response,
        create_refresh_token(
            identity=identity,
            additional_claims=claims,
            expires_delta=timedelta(seconds=left),
        ),
        max_age=left,
    )
