"""One id per request, carried into the jobs and outbox rows it starts.

The id comes from an incoming ``X-Request-ID`` header (the ingress or a
proxy may set one; only letters, digits, ``.``, ``_`` and ``-``, at most 64)
or is made here. It goes back as ``X-Request-ID`` on every response, into
the JSON log lines (``request_id``), into the body of a 500 (``requestId``,
so a person can quote it), into the ``request_id`` header of every Celery
task queued while the request runs, and into the ``hubrarequestid`` field of
every outbox envelope. A task sets it again as ``g.request_id``, so its log
lines carry the id of the request that started it.
"""

from __future__ import annotations

import re
from uuid import uuid4

from flask import Flask, g, has_app_context, request

HEADER = "X-Request-ID"
_VALID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def new_id() -> str:
    return uuid4().hex[:16]


def accept(value: str | None) -> str:
    """*value* when it is a usable id, else a new one."""
    if value and _VALID.match(value):
        return value
    return new_id()


def current() -> str | None:
    """The id of the request or task running now, if any."""
    if not has_app_context():
        return None
    return getattr(g, "request_id", None)


def init_app(app: Flask) -> None:
    @app.before_request
    def _assign() -> None:
        g.request_id = accept(request.headers.get(HEADER))

    @app.after_request
    def _echo(response):
        rid = current()
        if rid:
            response.headers[HEADER] = rid
        return response
