"""The club app asks for permission keys that exist, and shows each by name.

The app had asked for ``invoices.invoices.create`` while the API checks
``finance.invoices.create``: only admins (who pass every check) saw the
buttons, so a Treasurer role seemed to do nothing.
"""

import json
import re
from pathlib import Path

import pytest

from hubra.api.fields import iter_field_perms
from hubra.api.permissions import EXTRA_PERMISSIONS, _derive_perm_key

REPO = Path(__file__).resolve().parents[4]
FRONTEND = REPO / "app/frontend/src"
SEEDS = REPO / "app/backend/hubra/core/seed_data/translations"
# The settings screens are for admin roles only (the API checks is_admin).
ADMIN_ONLY = {"settings.settings.read", "settings.settings.write", "settings.settings.delete"}
_ASKED = re.compile(
    r"""(?:hasPermission\(\s*|permKey=)["']([a-z_]+\.[a-z_]+\.[a-z_.]+)["']"""
)


def _catalog(app) -> set[str]:
    keys = set()
    for rule in app.url_map.iter_rules():
        fn = app.view_functions.get(rule.endpoint)
        resource = getattr(fn, "_perm_resource", None)
        action = getattr(fn, "_perm_action", None)
        if resource and action:
            bp = rule.endpoint.rsplit(".", 1)[0] if "." in rule.endpoint else None
            keys.add(_derive_perm_key(bp, resource, action))
    with app.app_context():
        keys |= {m["key"] for m in iter_field_perms()}
    keys |= {m["key"] for m in EXTRA_PERMISSIONS}
    return keys


@pytest.mark.skipif(not FRONTEND.is_dir(), reason="the frontend is not next to the backend")
def test_club_app_asks_for_existing_keys(app):
    catalog = _catalog(app)
    asked = set()
    for path in FRONTEND.rglob("*.ts*"):
        asked |= set(_ASKED.findall(path.read_text(encoding="utf-8")))
    assert asked, "no permission checks found"
    assert sorted(asked - catalog - ADMIN_ONLY) == []


@pytest.mark.parametrize("locale", ["de-CH", "en-GB"])
def test_every_permission_has_a_name(app, locale):
    seed = json.loads((SEEDS / f"{locale}.json").read_text(encoding="utf-8"))
    named = {k.removeprefix("roles.perms.") for k in seed if k.startswith("roles.perms.")}
    missing = {k for k in _catalog(app) if k.replace(".", "_") not in named}
    assert sorted(missing) == []
