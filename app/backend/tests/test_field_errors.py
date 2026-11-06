"""Validation errors name their fields."""

from __future__ import annotations

from marshmallow import ValidationError

from hubra.core.errors import field_errors, validation_error


def test_flat_nested_and_list_messages():
    assert field_errors({"email": ["Not a valid email address."]}) == {
        "email": ["Not a valid email address."]
    }
    assert field_errors({"address": {"zip": ["Missing data."]}}) == {
        "address.zip": ["Missing data."]
    }
    assert field_errors({"items": {0: {"name": ["Required."]}}}) == {
        "items.0.name": ["Required."]
    }
    assert field_errors(["Dates don't fit."]) == {"_schema": ["Dates don't fit."]}


def test_validation_error_answer(app):
    with app.test_request_context("/"):
        res = validation_error(ValidationError({"email": ["Bad."]}))
    body = res.get_json()
    assert res.status_code == 400
    assert body["error"] == "VALIDATION_ERROR"
    assert body["fields"] == {"email": ["Bad."]}
    assert "email" in body["message"]  # the old text stays for older apps


def test_a_route_answers_with_fields(client, auth_headers):
    res = client.post("/api/v1/app/groups/", json={"name": 7}, headers=auth_headers)
    assert res.status_code in (400, 422)
    body = res.get_json()
    assert body["error"] == "VALIDATION_ERROR"
    assert "fields" in body and body["fields"]
