"""Every API path the frontends call leads to a backend route.

The SSO club search called /api/v1/platform/system/clubs after the API was
split into areas, a path no route serves: the platform backend answered the
browser's preflight with 404, so the browser showed a CORS error and the
search stayed empty. This test reads the frontend sources and matches each
literal ``apiFetch('/app|/global|/platform/...')`` path against the URL map.
"""

from __future__ import annotations

import re
from itertools import chain, product
from pathlib import Path

import pytest
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import RequestRedirect

REPO = Path(__file__).resolve().parents[3]
SOURCES = (
    "app/frontend/src",
    "app/sso-frontend/src",
    "app/admin-frontend/src",
    "app/support-frontend/src",
    "packages",
)

# apiFetch / apiFetchRaw, an optional type argument, then a literal path.
CALL = re.compile(
    r"\b(?:apiFetch|apiFetchRaw)\s*(?:<(?:[^<>]|<[^<>]*>)*>)?\(\s*"
    r"([`'\"])(/(?:app|global|platform)/[^`'\"]*)\1"
)
# Values tried for ${...} path segments (ints, any(approve, decline), slugs).
FILLS = ("1", "approve", "x")


def _frontend_calls() -> list[tuple[str, str]]:
    calls = []
    for src in SOURCES:
        for path in (REPO / src).rglob("*.ts*"):
            if "node_modules" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for m in CALL.finditer(text):
                calls.append((str(path.relative_to(REPO)), m.group(2)))
    return calls


def _candidates(literal: str) -> set[str]:
    # An expression cut off by a quote inside it builds the query string.
    raw = re.sub(r"\$\{[^}]*$", "", literal).split("?")[0]
    # A trailing ${...} is usually a query string (`${qs}`), but may be an id.
    bases = {raw, re.sub(r"\$\{[^}]*\}$", "", raw)}
    out = set()
    for base in bases:
        parts = re.split(r"\$\{[^}]*\}", base)
        for fills in product(FILLS, repeat=len(parts) - 1):
            out.add(
                "/api/v1" + "".join(chain.from_iterable(zip(parts, fills))) + parts[-1]
            )
    return out


def _routed(adapter, path: str) -> bool:
    try:
        adapter.match(path, method="GET")
    except (MethodNotAllowed, RequestRedirect):
        return True
    except NotFound:
        return False
    return True


def test_the_scan_finds_the_frontend_calls():
    calls = _frontend_calls()
    assert len(calls) > 100
    assert any(p.startswith("/global/clubs") for _f, p in calls)


def test_every_frontend_api_path_has_a_route(app):
    adapter = app.url_map.bind("localhost")
    missing = [
        f"{file}: {literal}"
        for file, literal in _frontend_calls()
        if not any(_routed(adapter, c) for c in _candidates(literal))
    ]
    assert not missing, "No backend route for:\n" + "\n".join(missing)


@pytest.mark.parametrize(
    "literal, expected",
    [
        ("/global/clubs${qs}", "/api/v1/global/clubs"),
        ("/platform/system/audit${s ? ", "/api/v1/platform/system/audit"),
        ("/app/members/${id}", "/api/v1/app/members/1"),
    ],
)
def test_candidates(literal, expected):
    assert expected in _candidates(literal)
