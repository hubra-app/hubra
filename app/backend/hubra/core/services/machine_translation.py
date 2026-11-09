"""Machine translation through DeepL, for posts in several languages.

Off until the platform sets ``translate.deepl_key`` (manage › Übersetzungen › Einstellungen).
The text goes to DeepL (an EU company, servers in the EU) only when a
writer presses "Translate"; nothing is translated in the background.
Markdown is kept: DeepL gets the text as it is and keeps the markup.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from hubra.core.errors import ApiError
from hubra.core.services import platform_settings

logger = logging.getLogger(__name__)

# DeepL's codes for our content languages.
_TARGET = {"de": "DE", "fr": "FR", "it": "IT", "en": "EN-GB"}
_SOURCE = {"de": "DE", "fr": "FR", "it": "IT", "en": "EN"}
TIMEOUT = 20


def available() -> bool:
    return bool(platform_settings.get("translate.deepl_key").strip())


def translate(texts: list[str], target: str, source: str | None = None) -> list[str]:
    """*texts* in *target*; empty strings stay empty.  Raises ApiError."""
    key = platform_settings.get("translate.deepl_key").strip()
    if not key:
        raise ApiError(503, "TRANSLATION_OFF", "Machine translation is not set up")
    if target not in _TARGET:
        raise ApiError(400, "VALIDATION_ERROR", f"Unknown language: {target}")
    todo = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
    out = list(texts)
    if not todo:
        return out
    base = (platform_settings.get("translate.deepl_url") or "").rstrip("/")
    if not base.startswith("https://"):
        raise ApiError(503, "TRANSLATION_OFF", "The DeepL address must be https")
    payload: dict = {"text": [t for _, t in todo], "target_lang": _TARGET[target]}
    if source in _SOURCE:
        payload["source_lang"] = _SOURCE[source]
    req = urllib.request.Request(  # noqa: S310 - fixed https address
        f"{base}/v2/translate",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"DeepL-Auth-Key {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        logger.warning("DeepL answered %s", exc.code)
        code = "TRANSLATION_QUOTA" if exc.code == 456 else "TRANSLATION_FAILED"
        raise ApiError(502, code, "The translation service refused the text") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise ApiError(502, "TRANSLATION_FAILED", "The translation service is not reachable") from None
    results = [t.get("text", "") for t in data.get("translations", [])]
    if len(results) != len(todo):
        raise ApiError(502, "TRANSLATION_FAILED", "The translation service answered oddly")
    for (i, _), text in zip(todo, results, strict=True):
        out[i] = text
    return out
