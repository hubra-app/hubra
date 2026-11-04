"""Early access: new features switched on club by club before everyone.

Every club runs the same build, so a "canary" here is not a second
deployment but a group of clubs that sees gated features first.

* A feature is gated by a flag in ``FLAGS`` (code).  Its **stage** is set in
  manage › Einstellungen › Früher Zugang: ``off`` (nobody), ``early`` (the
  early-access clubs) or ``all`` (every club; the flag can then be removed
  from the code in a later release).  Stages live in one platform setting
  row, ``features.stages``.
* A club is in the **early-access group** when ``tenant.settings
  ["early_access"]`` is true (manage › club).  A club can also have the
  feature forced on or off for itself (``tenant.settings["features"]``),
  whatever the stage.

Code asks ``is_on("key")`` (the current club) or ``is_on("key", tenant)``;
routes can use ``@require_feature("key")``; the club app reads
``GET /api/v1/features`` (``useFeature`` in the club app).

To add a flag: add it to ``FLAGS`` with German and English texts, gate the
code, and set its stage in manage.  See docs/feature-flags.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import wraps

from sqlalchemy.orm.attributes import flag_modified

from hubra.core.errors import ApiError
from hubra.core.extensions import db
from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.tenant import Tenant

STAGES = ("off", "early", "all")
_ROW = "features.stages"


@dataclass(frozen=True)
class Flag:
    key: str
    title_de: str
    title_en: str
    description_de: str = ""
    description_en: str = ""
    default: str = "off"


# The flags of this build.  Empty while nothing is in early access.
FLAGS: dict[str, Flag] = {}


def register(flag: Flag) -> Flag:
    """Add a flag (plugins and tests; core flags go in ``FLAGS`` directly)."""
    if flag.default not in STAGES:
        raise ValueError(f"default stage {flag.default!r}")
    FLAGS[flag.key] = flag
    return flag


def unregister(key: str) -> None:
    FLAGS.pop(key, None)


# ── Stages (platform) ───────────────────────────────────────────────────────


def _stored() -> dict[str, str]:
    row = db.session.get(PlatformSetting, _ROW)
    if row is None or not row.value:
        return {}
    try:
        data = json.loads(row.value)
    except ValueError:
        return {}
    return (
        {k: v for k, v in data.items() if v in STAGES} if isinstance(data, dict) else {}
    )


def stages() -> dict[str, str]:
    """Each known flag's stage (its default until manage sets one)."""
    stored = _stored()
    return {k: stored.get(k, f.default) for k, f in FLAGS.items()}


def set_stage(key: str, stage: str, actor_id: int | None = None) -> None:
    """Does NOT commit."""
    if key not in FLAGS:
        raise ApiError(404, "NOT_FOUND", f"Unknown feature {key!r}")
    if stage not in STAGES:
        raise ApiError(400, "VALIDATION_ERROR", "stage is off, early or all")
    stored = _stored()
    stored[key] = stage
    row = db.session.get(PlatformSetting, _ROW)
    if row is None:
        row = PlatformSetting(key=_ROW, secret=False)
        db.session.add(row)
    row.value = json.dumps(stored, sort_keys=True)
    row.updated_by = actor_id
    db.session.flush()


# ── Clubs ───────────────────────────────────────────────────────────────────


def in_early_access(tenant: Tenant | None) -> bool:
    return bool(tenant is not None and (tenant.settings or {}).get("early_access"))


def overrides(tenant: Tenant | None) -> dict[str, bool]:
    raw = ((tenant.settings or {}).get("features") or {}) if tenant else {}
    return {k: bool(v) for k, v in raw.items() if k in FLAGS and isinstance(v, bool)}


def set_club(tenant: Tenant, early_access=None, features: dict | None = None) -> None:
    """Join or leave the early-access group, and force flags on (true), off
    (false) or back to the stage (null).  Does NOT commit."""
    settings = dict(tenant.settings or {})
    if early_access is not None:
        if not isinstance(early_access, bool):
            raise ApiError(400, "VALIDATION_ERROR", "early_access is true or false")
        settings["early_access"] = early_access
    if features is not None:
        if not isinstance(features, dict):
            raise ApiError(400, "VALIDATION_ERROR", "features is an object")
        own = dict(settings.get("features") or {})
        for key, value in features.items():
            if key not in FLAGS:
                raise ApiError(400, "VALIDATION_ERROR", f"Unknown feature {key!r}")
            if value is None:
                own.pop(key, None)
            elif isinstance(value, bool):
                own[key] = value
            else:
                raise ApiError(400, "VALIDATION_ERROR", f"{key} is true, false or null")
        settings["features"] = own
    tenant.settings = settings
    flag_modified(tenant, "settings")


def is_on(key: str, tenant: Tenant | None = None, *, _stages=None) -> bool:
    """Whether *key* is on for *tenant* (default: the current club).  An
    unknown key is off."""
    if key not in FLAGS:
        return False
    if tenant is None:
        from hubra.core.tenant.context import current_tenant

        tenant = current_tenant()
    own = overrides(tenant)
    if key in own:
        return own[key]
    stage = (_stages or stages())[key]
    if stage == "all":
        return True
    if stage == "early":
        return in_early_access(tenant)
    return False


def for_club(tenant: Tenant | None) -> dict[str, bool]:
    """Every flag for one club, for the club app."""
    current = stages()
    return {k: is_on(k, tenant, _stages=current) for k in FLAGS}


def require_feature(key: str):
    """Route decorator: 404 while the feature is off for the club."""

    def wrap(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            if not is_on(key):
                raise ApiError(404, "NOT_FOUND", "Not found")
            return fn(*args, **kwargs)

        return inner

    return wrap


# ── Manage ──────────────────────────────────────────────────────────────────


def overview() -> dict:
    """Flags with their stage and who has them, and the early-access clubs."""
    from sqlalchemy import select

    current = stages()
    clubs = db.session.scalars(
        select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.name)
    ).all()
    early = [t for t in clubs if in_early_access(t)]
    flags = []
    for key, f in FLAGS.items():
        forced_on = [t.id for t in clubs if overrides(t).get(key) is True]
        forced_off = [t.id for t in clubs if overrides(t).get(key) is False]
        flags.append(
            {
                "key": key,
                "title_de": f.title_de,
                "title_en": f.title_en,
                "description_de": f.description_de,
                "description_en": f.description_en,
                "stage": current[key],
                "clubs_on": sum(1 for t in clubs if is_on(key, t, _stages=current)),
                "forced_on": forced_on,
                "forced_off": forced_off,
            }
        )
    return {
        "flags": flags,
        "early_access": [{"id": t.id, "name": t.name, "slug": t.slug} for t in early],
        "clubs_total": len(clubs),
    }


def club_json(tenant: Tenant) -> dict:
    current = stages()
    own = overrides(tenant)
    return {
        "early_access": in_early_access(tenant),
        "features": [
            {
                "key": k,
                "title_de": f.title_de,
                "title_en": f.title_en,
                "stage": current[k],
                "override": own.get(k),
                "on": is_on(k, tenant, _stages=current),
            }
            for k, f in FLAGS.items()
        ],
    }


def install(app) -> None:
    """``GET /api/v1/features``: the flags for the club of the request."""
    from flask import jsonify

    def _features():
        from hubra.core.tenant.context import current_tenant

        tenant = current_tenant()
        return jsonify({"features": for_club(tenant) if tenant else {}}), 200

    app.add_url_rule("/api/v1/app/features", "feature_flags", _features, methods=["GET"])
