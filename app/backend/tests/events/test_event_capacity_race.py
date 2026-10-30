"""Two sign-ups for an event's last place: one gets it, one waits.

Needs real row locks, so it only runs on Postgres (TEST_DATABASE_URL).
"""

import threading
import time
from datetime import date

import pytest

from hubra.api.events import services as event_services
from hubra.core.models.event import ClubEvent, EventRegistration
from hubra.core.models.member import Member
from hubra.core.models.user import User


def test_last_place_goes_to_one(app, db, seeded_db, monkeypatch):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("row locks need Postgres")

    member_ids = []
    for n in range(2):
        user = User(email=f"race{n}@test.ch", first_name="Race", last_name=str(n))
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()
        member = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
        db.session.add(member)
        db.session.flush()
        member_ids.append(member.id)
    event = ClubEvent(title="Fest", date=date(2030, 1, 1), type="Social", max_attendees=1)
    db.session.add(event)
    db.session.commit()
    event_id = event.id

    # Widen the gap between "is there a place?" and taking it.
    is_full = event_services.EventService._is_full

    def slow_is_full(ev, needed=1):
        full = is_full(ev, needed)
        time.sleep(0.3)
        return full

    monkeypatch.setattr(event_services.EventService, "_is_full", staticmethod(slow_is_full))

    errors = []

    def sign_up(member_id):
        try:
            with app.app_context():
                event_services.EventService.register(event_id, member_id)
                db.session.commit()
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=sign_up, args=(m,)) for m in member_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    db.session.expire_all()
    statuses = sorted(
        r.status for r in db.session.query(EventRegistration).filter_by(event_id=event_id)
    )
    assert statuses == ["registered", "waitlisted"]
