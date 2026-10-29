"""Transaction categories: names stay unique, and used or default ones stay."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

URL = "/api/v1/finance/transaction-categories"


def _create(client, auth_headers, name, color="#112233"):
    return client.post(URL, json={"name": name, "color": color}, headers=auth_headers)


def test_categories_are_listed_by_name(client, auth_headers, seeded_db):
    for name in ("Spenden", "Anlässe"):
        assert _create(client, auth_headers, name).status_code == 201
    names = [c["name"] for c in client.get(URL, headers=auth_headers).json]
    assert names == sorted(names) and {"Spenden", "Anlässe"} <= set(names)


def test_category_names_are_unique(client, auth_headers, seeded_db):
    first = _create(client, auth_headers, "Spenden").json
    other = _create(client, auth_headers, "Material").json
    assert _create(client, auth_headers, "Spenden").status_code == 409
    resp = client.patch(
        f"{URL}/{other['id']}", json={"name": "Spenden"}, headers=auth_headers
    )
    assert resp.status_code == 409
    # Keeping its own name (with a new colour) is fine.
    resp = client.patch(
        f"{URL}/{first['id']}",
        json={"name": "Spenden", "color": "#abcdef"},
        headers=auth_headers,
    )
    assert resp.status_code == 200 and resp.json["color"] == "#abcdef"


def test_bad_category_input_is_rejected(client, auth_headers, seeded_db):
    assert _create(client, auth_headers, "X", color="red").status_code == 400
    assert _create(client, auth_headers, "").status_code == 400
    resp = client.post(
        URL, json={"name": "X", "color": "#112233", "extra": 1}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_used_and_default_categories_cannot_be_deleted(
    client, auth_headers, seeded_db, db
):
    from hubra.core.models.finance import Transaction, TransactionCategory

    used = _create(client, auth_headers, "Beiträge").json
    unused = _create(client, auth_headers, "Leer").json
    default = TransactionCategory(name="Standard", color="#000000", is_default=True)
    db.session.add(default)
    db.session.add(
        Transaction(
            category_id=used["id"],
            date=date.today(),
            description="Beitrag",
            method="Bank Transfer",
            amount=Decimal("45.00"),
            type="income",
            status="Completed",
        )
    )
    db.session.commit()

    assert client.delete(f"{URL}/{used['id']}", headers=auth_headers).status_code == 409
    resp = client.delete(f"{URL}/{default.id}", headers=auth_headers)
    assert resp.status_code == 409
    assert (
        client.delete(f"{URL}/{unused['id']}", headers=auth_headers).status_code == 204
    )
    assert (
        client.delete(f"{URL}/{unused['id']}", headers=auth_headers).status_code == 404
    )
