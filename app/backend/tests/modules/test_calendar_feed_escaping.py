"""Event text can't add properties to a subscribed calendar."""

from datetime import date

from hubra.api.events.services import EventService
from hubra.core.models.event import ClubEvent


def test_line_breaks_cannot_add_calendar_properties(app, db):
    event = ClubEvent(
        title="Talk\rATTENDEE:mailto:x@example.com",
        date=date.today(),
        type="Meeting",
        meeting_url="https://meet.example/a\r\nATTACH:https://evil.example/x",
    )
    lines = EventService.generate_ical([event]).split("\r\n")
    assert not any(line.startswith(("ATTENDEE", "ATTACH")) for line in lines)
    assert not any(line.startswith("URL:") for line in lines)
