"""
Centralised error handling.

All API errors are returned as:
    { "error": "ERROR_CODE", "message": "Human-readable description" }

Usage inside a route:
    from hubra.core.errors import raise_error
    raise_error(404, "NOT_FOUND", "Member M-099 does not exist")

Or build a response manually:
    from hubra.core.errors import api_error
    return api_error("CONFLICT", "Email already registered", 409)
"""

from __future__ import annotations

from typing import NoReturn

from flask import Flask, jsonify
from sqlalchemy.exc import DataError
from werkzeug.exceptions import HTTPException


# ── Exception text for the user ──────────────────────────────────────────────


def error_message(exc: BaseException) -> str:
    """The text an exception was raised with, for an API answer.

    Only for exception classes whose message is written for the user
    (validation errors, InstallError, AppError, ...). It takes the first
    argument the exception was constructed with rather than ``str(exc)``,
    so a traceback or a wrapped cause never ends up in the response.
    """
    first = exc.args[0] if exc.args else None
    if isinstance(first, str) and first:
        return first
    return exc.__class__.__name__


# ── Response builder ─────────────────────────────────────────────────────────


def api_error(code: str, message: str, status: int, fields: dict | None = None):
    """Return a JSON error response with the standard envelope.

    *fields* names what is wrong per input field, ``{"email": ["Not a valid
    email address."]}``; the apps show it next to the field and translate
    it, instead of parsing *message*.
    """
    body: dict = {"error": code, "message": message}
    if fields:
        body["fields"] = fields
    response = jsonify(body)
    response.status_code = status
    return response


def field_errors(messages) -> dict[str, list[str]]:
    """Marshmallow's ``ValidationError.messages`` as ``{field: [problem]}``;
    nested fields become dotted names (``address.zip``), a list's items
    ``items.0.name``."""
    out: dict[str, list[str]] = {}

    def walk(prefix: str, value) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                walk(f"{prefix}.{key}" if prefix else str(key), inner)
        elif isinstance(value, (list, tuple)) and value and all(
            isinstance(v, str) for v in value
        ):
            out.setdefault(prefix or "_schema", []).extend(value)
        elif isinstance(value, (list, tuple)):
            for i, inner in enumerate(value):
                walk(f"{prefix}.{i}" if prefix else str(i), inner)
        else:
            out.setdefault(prefix or "_schema", []).append(str(value))

    walk("", messages if isinstance(messages, (dict, list)) else [str(messages)])
    return out


def validation_error(exc, status: int = 400):
    """The answer for a marshmallow ``ValidationError``: ``VALIDATION_ERROR``
    with the problems per field. ``message`` keeps the old text."""
    return api_error(
        "VALIDATION_ERROR", str(exc.messages), status, fields=field_errors(exc.messages)
    )


# ── Helper for raising from route logic ─────────────────────────────────────


class ApiError(Exception):
    """Raise this inside route handlers to trigger the JSON error handler."""

    def __init__(
        self, status: int, code: str, message: str, fields: dict | None = None
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields


def raise_error(
    status: int, code: str, message: str, fields: dict | None = None
) -> NoReturn:
    """Shorthand: raise_error(404, 'NOT_FOUND', 'Member M-099 does not exist').

    With *fields* (``{"email": ["..."]}``) the answer names the fields."""
    raise ApiError(status, code, message, fields)


# ── Registration ─────────────────────────────────────────────────────────────


def _internal_error():
    """A 500 with the request id, so the person can quote it to support."""
    from hubra.core import request_id

    response = jsonify(
        {
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "requestId": request_id.current(),
        }
    )
    response.status_code = 500
    return response


def register_error_handlers(app: Flask) -> None:
    """Attach JSON error handlers to *app*. Called from create_app()."""

    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return api_error(exc.code, exc.message, exc.status, getattr(exc, "fields", None))

    from sqlalchemy.exc import DataError

    @app.errorhandler(DataError)
    def handle_data_error(exc: DataError):
        # The database refused a value (a number too large for its column,
        # text that is not a number, ...): the request's input, not a bug.
        from hubra.core.extensions import db

        db.session.rollback()
        app.logger.warning("Value refused by the database: %s", exc.orig)
        return api_error(
            "VALIDATION_ERROR", "A value is too large or has the wrong format", 400
        )

    @app.errorhandler(400)
    def bad_request(exc):
        return api_error("VALIDATION_ERROR", str(exc.description), 400)

    @app.errorhandler(401)
    def unauthorized(exc):
        return api_error("UNAUTHORIZED", str(exc.description), 401)

    @app.errorhandler(403)
    def forbidden(exc):
        return api_error("FORBIDDEN", str(exc.description), 403)

    @app.errorhandler(404)
    def not_found(exc):
        return api_error("NOT_FOUND", str(exc.description), 404)

    @app.errorhandler(409)
    def conflict(exc):
        return api_error("CONFLICT", str(exc.description), 409)

    @app.errorhandler(422)
    def unprocessable(exc):
        return api_error("VALIDATION_ERROR", str(exc.description), 422)

    @app.errorhandler(DataError)
    def data_error(exc: DataError):
        # SQLSTATE class 22: a value the column can't hold (too long, out of
        # range, not a number). That is the request's fault, not the server's.
        from hubra.core.extensions import db

        db.session.rollback()
        app.logger.info("data_error: %s", exc.orig)
        return api_error(
            "VALIDATION_ERROR", "A value is too long or not valid for its field.", 400
        )

    @app.errorhandler(AttributeError)
    @app.errorhandler(TypeError)
    def body_type_error(exc: Exception):
        # Routes read their body with body.get(...) or "key" in body; a JSON
        # array or number there is the request's fault.
        from flask import request

        body = request.get_json(silent=True)
        if body is not None and not isinstance(body, dict):
            return api_error(
                "VALIDATION_ERROR", "The request body must be a JSON object.", 400
            )
        if app.testing or app.config.get("PROPAGATE_EXCEPTIONS"):
            raise exc  # a real bug: let tests (and debug) see it
        from hubra.core.services import error_tracker

        error_tracker.capture(exc)
        app.logger.exception("Unhandled exception: %s", exc)
        return _internal_error()

    @app.errorhandler(500)
    def internal_error(exc):
        app.logger.exception("Unhandled exception: %s", exc)
        return _internal_error()

    # Catch-all for other Werkzeug HTTP exceptions not listed above
    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return api_error(
            exc.name.upper().replace(" ", "_"),
            exc.description or exc.name,
            exc.code or 500,
        )
