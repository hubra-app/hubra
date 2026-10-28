"""PATCH /tiers/<id> checks the values it is given."""

import pytest


@pytest.fixture
def tier_id(db, seeded_db):
    return seeded_db["tier"].id


@pytest.mark.parametrize(
    "body",
    [
        {"percentage_value": "abc"},
        {"coefficient": "NaN"},
        {"coefficient": {"x": 1}},
        {"round_to": "five"},
        {"round_to": [5]},
        {"deduct_tier_ids": ["a"]},
        {"deduct_tier_ids": "1,2"},
    ],
)
def test_bad_numbers_are_a_400(client, auth_headers, tier_id, body):
    resp = client.patch(f"/api/v1/tiers/{tier_id}", json=body, headers=auth_headers)
    assert resp.status_code == 400, resp.get_data(as_text=True)


def test_numbers_are_stored(client, auth_headers, tier_id):
    resp = client.patch(
        f"/api/v1/tiers/{tier_id}",
        json={
            "price_type": "percentage",
            "percentage_value": "12.5",
            "coefficient": 2,
            "round_to": "5",
            "deduct_tier_ids": [1, "2"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["percentage_value"] == 12.5
    assert body["coefficient"] == 2
    assert body["round_to"] == 5
    assert body["deduct_tier_ids"] == [1, 2]
