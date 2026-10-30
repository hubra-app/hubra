"""The club app's built-in texts and the backend seed say the same thing.

The club app shows the seed (from the database) when it has loaded and its
own copy before that, so a key in only one of them shows the code's fallback
text, and a different value makes a text change once the page has loaded.
"""

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
SEEDS = REPO / "app/backend/hubra/core/seed_data/translations"
FRONTEND = REPO / "app/frontend/src/locales"
LOCALES = {"de-CH": "de-CH", "en-GB": "en"}
# Texts of the emails the backend sends; the club app never shows them.
BACKEND_ONLY = "mail.email."


def _flat(tree: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in tree.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flat(value, full))
        else:
            out[full] = value
    return out


def _load(path: Path) -> dict[str, str]:
    return _flat(json.loads(path.read_text(encoding="utf-8")))


pytestmark = pytest.mark.skipif(
    not FRONTEND.is_dir(), reason="the frontend is not next to the backend"
)


@pytest.mark.parametrize("locale", LOCALES)
def test_frontend_and_seed_match(locale):
    seed = _load(SEEDS / f"{locale}.json")
    frontend = _load(FRONTEND / LOCALES[locale] / "translation.json")
    shown = {k: v for k, v in seed.items() if not k.startswith(BACKEND_ONLY)}
    assert sorted(set(frontend) - set(shown)) == [], "missing from the seed"
    assert sorted(set(shown) - set(frontend)) == [], "missing from the frontend"
    differ = {k: (frontend[k], shown[k]) for k in frontend if frontend[k] != shown[k]}
    assert differ == {}


def test_every_key_has_both_languages():
    de = _load(SEEDS / "de-CH.json")
    en = _load(SEEDS / "en-GB.json")
    assert sorted(set(de) ^ set(en)) == []
    assert [k for k, v in de.items() if not v.strip()] == []
    assert [k for k, v in en.items() if not v.strip()] == []


def test_german_uses_swiss_spelling():
    de = _load(SEEDS / "de-CH.json")
    assert [k for k, v in de.items() if "ß" in v] == []
