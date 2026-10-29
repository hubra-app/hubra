"""A value the database refuses is a 400, not a 500."""

from sqlalchemy.exc import DataError


def test_a_value_too_long_for_its_column_is_a_400(app):
    exc = DataError("INSERT ...", {}, Exception("value too long for type varchar(255)"))
    with app.test_request_context():
        resp = app.handle_user_exception(exc)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "VALIDATION_ERROR"
