"""Clubs can pick their own event types (events module setting event_types)."""

from unittest.mock import patch

import pytest
from marshmallow import ValidationError

from hubra.core.schemas.event import ClubEventCreateSchema, club_event_types


def _config(value):
    return patch(
        "hubra.core.modules.state.get_config",
        return_value={"event_types": value},
    )


def test_built_in_types_without_a_list(app):
    with app.app_context(), _config(""):
        assert club_event_types() == ["Workshop", "Social", "Certification", "Meeting"]


def test_own_types_are_accepted(app):
    with app.app_context(), _config(" Training, Match ,,Versammlung "):
        assert club_event_types() == ["Training", "Match", "Versammlung"]
        data = ClubEventCreateSchema().load(
            {"title": "Spiel", "date": "2026-11-02", "type": "Match"}
        )
        assert data["type"] == "Match"
        # Built-in types stay valid for older events.
        ClubEventCreateSchema().load(
            {"title": "Alt", "date": "2026-11-02", "type": "Workshop"}
        )
        with pytest.raises(ValidationError):
            ClubEventCreateSchema().load(
                {"title": "X", "date": "2026-11-02", "type": "Party"}
            )
