"""flask seed brings stored texts up to date with the shipped ones."""

from pathlib import Path

from hubra.core.models.translation import Translation
from hubra.core.seeds import refresh_shipped_translations

SEEDS = Path(__file__).resolve().parents[2] / "hubra/core/seed_data/translations"


def test_a_text_that_is_its_own_key_gets_the_shipped_text(app, db):
    db.session.add(Translation(locale="de-CH", key="common.save", value="common.save"))
    db.session.add(Translation(locale="de-CH", key="common.cancel", value="Lass es"))
    db.session.commit()

    refresh_shipped_translations(db.session, SEEDS)

    rows = {t.key: t.value for t in db.session.query(Translation).filter_by(locale="de-CH")}
    assert rows["common.save"] == "Speichern"
    # Edited by the club: left alone.
    assert rows["common.cancel"] == "Lass es"
