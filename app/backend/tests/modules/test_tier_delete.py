"""Deleting a tier nobody is on."""


def test_delete_tier_someone_applied_for(client, auth_headers, seeded_db, db):
    """An open application that asked for the tier keeps going, without a
    tier wish, instead of blocking the delete."""
    from hubra.core.models.application import Application
    from hubra.core.models.member import MembershipTier

    tier = MembershipTier(name="Weekend", price_chf=20, color="#123456")
    db.session.add(tier)
    db.session.flush()
    application = Application(name="Ada", email="ada@test.ch", wants_tier_id=tier.id)
    db.session.add(application)
    db.session.commit()
    tier_id, application_id = tier.id, application.id

    resp = client.delete(f"/api/v1/tiers/{tier_id}", headers=auth_headers)
    assert resp.status_code in (200, 204), resp.get_data(as_text=True)

    db.session.expunge_all()
    assert db.session.get(MembershipTier, tier_id) is None
    assert db.session.get(Application, application_id).wants_tier_id is None
