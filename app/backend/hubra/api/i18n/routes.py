"""i18n blueprint — the platform's translations.

The texts belong to the platform: every club reads the same ones, and only
platform admins (global permission ``platform.settings``) change them, from
the manager portal. Clubs suggest changes (see ``requests_routes``).
"""

from __future__ import annotations

import csv
import io
import json
import logging

from flask import Blueprint, Response, jsonify, request

from marshmallow import Schema, fields, validate

from hubra.api.permissions import permission_required, require_global_permission
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.api.i18n.services import (
    bulk_upsert,
    compute_is_stale,
    copy_defaults,
    delete_translation,
    duplicate_locale,
    _get_stale_threshold_seconds,
    get_available_locales,
    get_etag,
    get_flagged,
    get_translations,
    get_translations_dict,
    upsert_translation,
    import_translations,
    report_missing_keys,
)

logger = logging.getLogger(__name__)

i18n_bp = Blueprint("i18n_bp", __name__)

_platform_admin = require_global_permission("platform.settings")


def canonical_locale(code: str) -> str:
    """BCP 47 casing: "de-ch" and "DE-CH" are the shipped "de-CH".

    Rows are stored under the exact code, and the club app reads them under
    the canonical one, so a second spelling would be a language of its own
    that the app never shows.
    """
    parts = code.replace("_", "-").split("-")
    out = [parts[0].lower()]
    for part in parts[1:]:
        out.append(part.upper() if len(part) == 2 else part.title() if len(part) == 4 else part.lower())
    return "-".join(out)


@i18n_bp.url_value_preprocessor
def _canonical_locale_arg(_endpoint, values):
    if values and isinstance(values.get("locale"), str):
        values["locale"] = canonical_locale(values["locale"])


class TranslationWriteSchema(Schema):
    key = fields.String(required=True, validate=validate.Length(min=1))
    value = fields.String(required=True)
    alias_for = fields.String(load_default=None)


_write_schema = TranslationWriteSchema()


# ── GET /i18n/languages ────────────────────────────────────────────────────


@i18n_bp.get("/languages")
def get_languages():
    locales = get_available_locales()
    return jsonify(locales), 200


# ── GET /i18n/<locale> ──────────────────────────────────────────────────────


@i18n_bp.get("/<string:locale>")
def get_i18n(locale: str):
    if request.args.get("list", "0") == "1":
        # The editor's view (defaults, usage, flags) is for translators only;
        # the plain dictionary below stays public for the sign-in pages.
        return _translation_rows(locale)

    etag = get_etag(locale)
    if_none_match = request.headers.get("If-None-Match")
    if etag and if_none_match and etag == if_none_match:
        return Response(status=304)

    data = get_translations_dict(locale)

    resp = jsonify(data)
    if etag:
        resp.headers["ETag"] = etag
    return resp, 200


@_platform_admin
def _translation_rows(locale: str):
    rows = get_translations(locale)
    threshold = _get_stale_threshold_seconds()
    data = [
        {
            "id": r.id,
            "locale": r.locale,
            "key": r.key,
            "value": r.value,
            "default_value": r.default_value,
            "needs_attention": r.needs_attention,
            "is_missing": r.is_missing,
            "is_stale": compute_is_stale(r.last_used_at, threshold),
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "alias_for": r.alias_for,
        }
        for r in rows
    ]
    return jsonify(data), 200


# ── PATCH /i18n/<locale> ────────────────────────────────────────────────────


@i18n_bp.patch("/<string:locale>")
@_platform_admin
def patch_i18n(locale: str):
    body = request.get_json(silent=True)
    if not body or not isinstance(body, list):
        return api_error(
            "VALIDATION_ERROR", "Expected a JSON array of translation objects", 400
        )

    entries: list[dict] = []
    for item in body:
        try:
            validated = _write_schema.load(item)
        except Exception as exc:
            return api_error("VALIDATION_ERROR", str(exc), 400)
        entries.append(validated)

    try:
        updated = bulk_upsert(locale, entries, updated_by_id=None)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to bulk-upsert translations")
        return api_error("SERVER_ERROR", str(exc), 500)

    return jsonify(
        {
            "upserted": len(updated),
            "locale": locale,
        }
    ), 200


# ── POST /i18n/<locale> ─────────────────────────────────────────────────────


@i18n_bp.post("/<string:locale>")
@_platform_admin
def post_translation(locale: str):
    body = request.get_json(silent=True) or {}
    try:
        data = _write_schema.load(body)
    except Exception as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    try:
        obj = upsert_translation(
            locale=locale,
            key=data["key"],
            value=data["value"],
            updated_by_id=None,
            alias_for=data.get("alias_for"),
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to upsert translation")
        return api_error("SERVER_ERROR", str(exc), 500)

    return jsonify(
        {
            "id": obj.id,
            "locale": obj.locale,
            "key": obj.key,
            "value": obj.value,
        }
    ), 201


# ── DELETE /i18n/<locale>/<path:key> ────────────────────────────────────────


@i18n_bp.delete("/<string:locale>/<path:key>")
@_platform_admin
def delete_i18n(locale: str, key: str):
    try:
        deleted = delete_translation(locale, key)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to delete translation")
        return api_error("SERVER_ERROR", str(exc), 500)

    if deleted == 0:
        return api_error("NOT_FOUND", "Translation not found", 404)

    return jsonify({"deleted": True, "count": deleted}), 200


# ── POST /i18n/<locale>/duplicate ──────────────────────────────────────────────


class DuplicateLocaleSchema(Schema):
    source = fields.String(required=True, validate=validate.Length(min=1))
    copy_values = fields.Boolean(load_default=False)


_dup_schema = DuplicateLocaleSchema()


@i18n_bp.post("/<string:locale>/duplicate")
@_platform_admin
def duplicate_i18n(locale: str):
    body = request.get_json(silent=True) or {}
    try:
        data = _dup_schema.load(body)
    except Exception as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    source = canonical_locale(data["source"])
    copy_values = data.get("copy_values", False)

    if source == locale:
        return api_error(
            "VALIDATION_ERROR", "Source and target locale must differ", 400
        )

    available = get_available_locales()
    if source not in available:
        return api_error(
            "NOT_FOUND", f"Source locale '{source}' has no translations", 404
        )

    try:
        inserted = duplicate_locale(
            source_locale=source,
            target_locale=locale,
            copy_values=copy_values,
            updated_by_id=None,
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to duplicate locale")
        return api_error("SERVER_ERROR", str(exc), 500)

    return jsonify(
        {
            "locale": locale,
            "source": source,
            "inserted": inserted,
            "copy_values": copy_values,
        }
    ), 201


# ── POST /i18n/<locale>/copy-defaults ──────────────────────────────────────────


@i18n_bp.post("/<string:locale>/copy-defaults")
@_platform_admin
def copy_defaults_i18n(locale: str):
    try:
        filled = copy_defaults(locale)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to copy defaults for locale %s", locale)
        return api_error("SERVER_ERROR", str(exc), 500)

    return jsonify({"locale": locale, "filled": filled}), 200


# ── GET /i18n/<locale>/export ──────────────────────────────────────────────


class ExportQuerySchema(Schema):
    format = fields.String(
        load_default="json", validate=validate.OneOf(["json", "csv"])
    )


_export_query_schema = ExportQuerySchema()


@i18n_bp.get("/<string:locale>/export")
@_platform_admin
def export_i18n(locale: str):
    try:
        query = _export_query_schema.load(request.args)
    except Exception as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    fmt = query.get("format", "json")
    rows = get_translations(locale)
    resolved = get_translations_dict(locale)

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["key", "value"])
        for row in rows:
            writer.writerow([row.key, resolved.get(row.key, row.value)])
        content = output.getvalue()
        resp = Response(
            content,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=translations_{locale}.csv"
            },
        )
        return resp, 200

    resp = jsonify(resolved)
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=translations_{locale}.json"
    )
    return resp, 200


# ── POST /i18n/<locale>/import ─────────────────────────────────────────────


@i18n_bp.post("/<string:locale>/import")
@_platform_admin
def import_i18n(locale: str):
    try:
        query = _export_query_schema.load(request.args)
    except Exception as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    fmt = query.get("format", "json")

    if "file" not in request.files:
        return api_error("VALIDATION_ERROR", "No file uploaded", 400)

    uploaded_file = request.files["file"]
    if not uploaded_file.filename:
        return api_error("VALIDATION_ERROR", "No file selected", 400)

    max_bytes = 2 * 1024 * 1024  # 2 MiB cap for translation imports
    content_length = request.content_length or 0
    if content_length and content_length > max_bytes:
        return api_error(
            "VALIDATION_ERROR",
            f"File too large (max {max_bytes // 1024} KiB)",
            413,
        )

    try:
        # utf-8-sig: a file saved by Excel starts with a byte order mark.
        file_content = uploaded_file.stream.read(max_bytes + 1).decode("utf-8-sig")
        if len(file_content.encode("utf-8")) > max_bytes:
            return api_error(
                "VALIDATION_ERROR",
                f"File too large (max {max_bytes // 1024} KiB)",
                413,
            )
    except Exception as exc:
        return api_error("VALIDATION_ERROR", f"Could not read file: {exc}", 400)

    entries: list[dict[str, str]] = []

    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(file_content), fieldnames=["key", "value"])
        for n, row in enumerate(reader):
            if n == 0 and (row.get("key") or "").strip() == "key":
                continue  # the header line the export writes
            if row.get("key") and row.get("key", "").strip():
                entries.append(
                    {"key": row["key"].strip(), "value": row.get("value", "") or ""}
                )
    elif fmt == "json":
        try:
            parsed = json.loads(file_content)
        except json.JSONDecodeError as exc:
            return api_error("VALIDATION_ERROR", f"Invalid JSON: {exc}", 400)

        if not isinstance(parsed, dict):
            return api_error(
                "VALIDATION_ERROR",
                "JSON must be a flat object of key-value pairs",
                400,
            )

        for key, value in parsed.items():
            if key and str(key).strip():
                entries.append(
                    {
                        "key": str(key).strip(),
                        "value": str(value) if value is not None else "",
                    }
                )

    if not entries:
        return api_error("VALIDATION_ERROR", "No valid entries found in file", 400)

    try:
        count = import_translations(
            locale,
            entries,
            updated_by_id=None,
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to import translations")
        return api_error("SERVER_ERROR", str(exc), 500)

    return jsonify(
        {
            "locale": locale,
            "imported": count,
        }
    ), 201


# ── POST /i18n/<locale>/report ──────────────────────────────────────────────


class ReportKeyItemSchema(Schema):
    key = fields.String(required=True, validate=validate.Length(min=1))
    default_value = fields.String(load_default=None, allow_none=True)


class ReportKeysSchema(Schema):
    keys = fields.List(fields.Nested(ReportKeyItemSchema), required=True)


_report_schema = ReportKeysSchema()


@i18n_bp.post("/<string:locale>/report")
@_platform_admin
def report_keys(locale: str):
    body = request.get_json(silent=True) or {}
    try:
        data = _report_schema.load(body)
    except Exception as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    keys = data["keys"]
    if not keys:
        return jsonify({"flagged": 0}), 200

    from flask import current_app

    if current_app.config.get("TESTING"):
        try:
            flagged = report_missing_keys(locale, keys)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.exception("Failed to report missing keys")
            return api_error("SERVER_ERROR", str(exc), 500)
        return jsonify({"flagged": flagged}), 200

    from hubra.core.tasks.i18n_tasks import report_missing_keys_task

    report_missing_keys_task.delay(locale, keys)
    return jsonify({"flagged": 0}), 200


# ── GET /i18n/<locale>/flagged ──────────────────────────────────────────────


@i18n_bp.get("/<string:locale>/flagged")
@_platform_admin
def get_flagged_i18n(locale: str):
    rows = get_flagged(locale)
    threshold = _get_stale_threshold_seconds()
    data = [
        {
            "id": r.id,
            "locale": r.locale,
            "key": r.key,
            "value": r.value,
            "default_value": r.default_value,
            "needs_attention": r.needs_attention,
            "is_missing": r.is_missing,
            "is_stale": compute_is_stale(r.last_used_at, threshold),
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "alias_for": r.alias_for,
        }
        for r in rows
    ]
    return jsonify(data), 200


# ── Club suggestions: /i18n/requests ────────────────────────────────────────


class SuggestionSchema(Schema):
    locale = fields.String(required=True, validate=validate.Length(min=2, max=10))
    key = fields.String(required=True, validate=validate.Length(min=1, max=255))
    value = fields.String(required=True, validate=validate.Length(min=1, max=5000))
    note = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=2000))


_suggestion_schema = SuggestionSchema()


def _club_id() -> int | None:
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    return tenant.id if tenant is not None else None


@i18n_bp.get("/requests")
@permission_required("i18n", "write", "Suggest translations")
def list_club_requests():
    """This club's suggestions, newest first."""
    from hubra.api.i18n import requests as suggestions

    club = _club_id()
    if club is None:
        return api_error("NO_TENANT", "No club selected", 400)
    return jsonify([r.to_dict() for r in suggestions.for_club(club)]), 200


@i18n_bp.post("/requests")
@permission_required("i18n", "write", "Suggest translations")
def create_club_request():
    """Suggest a new text; a platform admin accepts or rejects it."""
    from flask_jwt_extended import get_jwt

    from hubra.api.i18n import requests as suggestions

    club = _club_id()
    if club is None:
        return api_error("NO_TENANT", "No club selected", 400)
    try:
        data = _suggestion_schema.load(request.get_json(silent=True) or {})
    except Exception as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)
    user_id = get_jwt().get("user_id")
    try:
        req = suggestions.submit(
            club,
            int(user_id) if user_id is not None else None,
            canonical_locale(data["locale"]),
            data["key"],
            data["value"],
            data.get("note"),
        )
        db.session.commit()
    except suggestions.RequestError as exc:
        db.session.rollback()
        return api_error("VALIDATION_ERROR", str(exc), 400)
    return jsonify(req.to_dict()), 201
