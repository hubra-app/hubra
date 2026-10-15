"""
Centralised error handling.

All API errors are returned as:
    { "error": "ERROR_CODE", "message": "Human-readable description" }

Usage inside a route:
    from vollbuild.core.errors import raise_error
    raise_error(404, "NOT_FOUND", "Member M-099 does not exist")

Or build a response manually:
    from vollbuild.core.errors import api_error
    return api_error("CONFLICT", "Email already registered", 409)
"""

from __future__ import annotations

from typing import NoReturn

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


# ── Response builder ─────────────────────────────────────────────────────────


def api_error(code: str, message: str, status: int):
    """Return a JSON error response with the standard envelope."""
    response = jsonify({"error": code, "message": message})
    response.status_code = status
    return response


# ── Helper for raising from route logic ─────────────────────────────────────


class ApiError(Exception):
    """Raise this inside route handlers to trigger the JSON error handler."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def raise_error(status: int, code: str, message: str) -> NoReturn:
    """Shorthand: raise_error(404, 'NOT_FOUND', 'Member M-099 does not exist')."""
    raise ApiError(status, code, message)


# ── Registration ─────────────────────────────────────────────────────────────


def register_error_handlers(app: Flask) -> None:
    """Attach JSON error handlers to *app*. Called from create_app()."""

    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return api_error(exc.code, exc.message, exc.status)

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

    @app.errorhandler(500)
    def internal_error(exc):
        app.logger.exception("Unhandled exception: %s", exc)
        return api_error("INTERNAL_ERROR", "An unexpected error occurred.", 500)

    # Catch-all for other Werkzeug HTTP exceptions not listed above
    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return api_error(
            exc.name.upper().replace(" ", "_"),
            exc.description or exc.name,
            exc.code or 500,
        )
