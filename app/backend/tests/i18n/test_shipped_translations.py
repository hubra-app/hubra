"""The club app's built-in texts and the backend seed say the same thing.

The club app shows the seed (from the database) when it has loaded and its
own copy before that, so a key in only one of them shows the code's fallback
text, and a different value makes a text change once the page has loaded.
"""

import json
from pathlib import Path

import pytest

from hubra.core.seeds import load_shipped_translations

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


def _seed(locale: str) -> dict[str, str]:
    return _flat(load_shipped_translations(SEEDS, locale))


def _frontend(lang: str) -> dict[str, str]:
    """Each locales/<lang>/<feature>.json holds the texts under <feature>."""
    out: dict[str, str] = {}
    for path in sorted((FRONTEND / lang).glob("*.json")):
        out.update(_flat(json.loads(path.read_text(encoding="utf-8")), path.stem))
    return out


pytestmark = pytest.mark.skipif(
    not FRONTEND.is_dir(), reason="the frontend is not next to the backend"
)


@pytest.mark.parametrize("locale", LOCALES)
def test_frontend_and_seed_match(locale):
    seed = _seed(locale)
    frontend = _frontend(LOCALES[locale])
    shown = {k: v for k, v in seed.items() if not k.startswith(BACKEND_ONLY)}
    assert sorted(set(frontend) - set(shown)) == [], "missing from the seed"
    assert sorted(set(shown) - set(frontend)) == [], "missing from the frontend"
    differ = {k: (frontend[k], shown[k]) for k in frontend if frontend[k] != shown[k]}
    assert differ == {}


def test_every_key_has_both_languages():
    de = _seed("de-CH")
    en = _seed("en-GB")
    assert sorted(set(de) ^ set(en)) == []
    assert [k for k, v in de.items() if not v.strip()] == []
    assert [k for k, v in en.items() if not v.strip()] == []


def test_german_uses_swiss_spelling():
    de = _seed("de-CH")
    assert [k for k, v in de.items() if "ß" in v] == []


@pytest.mark.parametrize("locale", LOCALES)
def test_seed_files_hold_their_own_feature(locale):
    # seed_data/translations/<locale>/<feature>.json holds only <feature>.* keys,
    # and no key is in two files.
    seen: dict[str, str] = {}
    wrong, twice = [], []
    for path in sorted((SEEDS / locale).glob("*.json")):
        for key in json.loads(path.read_text(encoding="utf-8")):
            if key.split(".")[0] != path.stem:
                wrong.append(f"{path.name}: {key}")
            if key in seen:
                twice.append(f"{key} ({seen[key]}, {path.name})")
            seen[key] = path.name
    assert wrong == [], "key in the wrong feature file"
    assert twice == []
