# ruff: noqa: F811 - pytest fixtures imported from another test module
"""One statement per member: open items handed over by modules (or added
by hand) go on one invoice per member (roadmap idea 29)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from hubra.core.contracts import SYSTEM, call
from hubra.core.extensions import db
from hubra.core.models.finance import Invoice, OpenItem
from tests.authz.test_invoice_pdf import banking  # noqa: F401, F811 - fixture
from tests.settings.test_settings_kv import _login, _make_role_and_member

URL = "/api/v1/app/finance/open-items"


@pytest.fixture
def collect(monkeypatch):
    """Set the club's collecting (finance settings collect_items and
    collect_min_amount)."""
    import hubra.core.modules as modules

    real = modules.get_config

    def set_(cycle: str, minimum: float = 0.0) -> None:
        def get_config(code, *a, **kw):
            conf = dict(real(code, *a, **kw))
            if code == "finance":
                conf.update(collect_items=cycle, collect_min_amount=minimum)
            return conf

        monkeypatch.setattr(modules, "get_config", get_config)

    return set_


def _invoices() -> int:
    return db.session.scalar(select(func.count()).select_from(Invoice))


@pytest.fixture
def member_id(seeded_db):
    return seeded_db["admin"].id


def test_with_collecting_off_an_item_is_billed_at_once(app, member_id):
    out = call(
        "finance.open_item.add",
        {
            "member_id": member_id,
            "amount": "4.50",
            "text": "Kaffee",
            "source_ref": "tab-1",
        },
        actor=SYSTEM,
    )
    assert out["invoice_id"] is not None
    invoice = db.session.get(Invoice, out["invoice_id"])
    assert invoice.amount == Decimal("4.50") and invoice.description == "Kaffee"


def test_collected_monthly_with_a_minimum(app, member_id, collect):
    from hubra.api.finance.tasks import _collect_open_items

    collect("monthly", 10)
    for ref, amount in (("a", "4.50"), ("b", "3.00")):
        out = call(
            "finance.open_item.add",
            {
                "member_id": member_id,
                "amount": amount,
                "text": f"Getränk {ref}",
                "source_ref": ref,
            },
            actor=SYSTEM,
        )
        assert out["invoice_id"] is None
    before = _invoices()
    assert _collect_open_items(today=date(2030, 6, 15))  # not the 1st
    _collect_open_items(today=date(2030, 7, 1))
    assert _invoices() == before  # 7.50 is below the minimum: waits

    call(
        "finance.open_item.add",
        {
            "member_id": member_id,
            "amount": "5.00",
            "text": "Getränk c",
            "source_ref": "c",
        },
        actor=SYSTEM,
    )
    _collect_open_items(today=date(2030, 7, 1))
    assert _invoices() == before + 1
    items = db.session.scalars(select(OpenItem)).all()
    invoice_ids = {i.invoice_id for i in items}
    assert len(invoice_ids) == 1 and None not in invoice_ids
    invoice = db.session.get(Invoice, invoice_ids.pop())
    assert invoice.amount == Decimal("12.50")


def test_quarterly_only_on_the_first_of_a_quarter(app):
    from hubra.api.finance.open_items import is_billing_day

    assert is_billing_day(date(2030, 4, 1), "quarterly")
    assert not is_billing_day(date(2030, 5, 1), "quarterly")
    assert is_billing_day(date(2030, 5, 1), "monthly")
    assert not is_billing_day(date(2030, 5, 1), "off")


def test_a_reference_counts_once_and_is_taken_back_until_billed(
    app, member_id, collect
):
    from hubra.core.contracts import Refused

    collect("monthly")
    item = {"member_id": member_id, "amount": "2", "text": "Bier", "source_ref": "x"}
    call("finance.open_item.add", item, actor=SYSTEM)
    with pytest.raises(Refused) as err:
        call("finance.open_item.add", item, actor=SYSTEM)
    assert err.value.code == "ALREADY_ADDED"
    assert call("finance.open_item.remove", {"source_ref": "x"}, actor=SYSTEM)[
        "removed"
    ]
    assert not call("finance.open_item.remove", {"source_ref": "x"}, actor=SYSTEM)[
        "removed"
    ]


def test_treasurer_lists_adds_bills_and_sees_the_lines(
    client, auth_headers, member_id, collect
):
    collect("quarterly")
    for text, amount in (("Kursbeitrag", 30), ("Material", 12.5)):
        resp = client.post(
            URL,
            json={"member_id": member_id, "amount": amount, "text": text},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.get_json()
    listed = client.get(URL, headers=auth_headers).get_json()
    assert listed["cycle"] == "quarterly"
    assert [i["text"] for i in listed["items"]] == ["Kursbeitrag", "Material"]
    assert listed["items"][0]["source"] == "finance"

    resp = client.post(f"{URL}/bill", json={}, headers=auth_headers)
    assert resp.status_code == 200
    (invoice_id,) = resp.get_json()["invoices"]
    assert client.get(URL, headers=auth_headers).get_json()["items"] == []
    detail = client.get(
        f"/api/v1/app/finance/invoices/{invoice_id}", headers=auth_headers
    )
    body = detail.get_json()
    assert float(body["amount"]) == 42.5
    assert [i["text"] for i in body["items"]] == ["Kursbeitrag", "Material"]
    # A billed item can't be taken back.
    item_id = body["items"][0]["id"]
    assert client.delete(f"{URL}/{item_id}", headers=auth_headers).status_code == 409


def test_bad_input_and_rights(client, app, auth_headers, seeded_db, member_id):
    assert (
        client.post(
            URL, json={"member_id": member_id, "amount": 1}, headers=auth_headers
        ).status_code
        == 400
    )
    assert (
        client.post(
            URL,
            json={"member_id": 99999, "amount": 1, "text": "x"},
            headers=auth_headers,
        ).status_code
        == 404
    )
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        db, seeded_db["tier"], name="Reader", permission_keys=["posts.posts.read"]
    )
    client.post("/api/v1/auth/logout")
    _login(client, "reader@test.ch")
    assert client.get(URL).status_code == 403
    assert client.post(f"{URL}/bill", json={}).status_code == 403
    client.post("/api/v1/auth/logout")
    assert client.get(URL).status_code == 401


def test_the_pdf_lists_the_items(
    client, auth_headers, member_id, collect, banking, monkeypatch
):
    import flask

    from tests.authz.test_invoice_pdf import QR_IBAN

    collect("monthly")
    banking(QR_IBAN)
    for text in ("Kaffee", "Gipfeli"):
        client.post(
            URL,
            json={"member_id": member_id, "amount": 3, "text": text},
            headers=auth_headers,
        )
    (invoice_id,) = client.post(
        f"{URL}/bill", json={}, headers=auth_headers
    ).get_json()["invoices"]

    seen = {}
    render = flask.render_template

    def spy(name, **context):
        if name == "invoice/invoice.html":
            seen.update(context)
        return render(name, **context)

    monkeypatch.setattr(flask, "render_template", spy)
    resp = client.get(
        f"/api/v1/finance/invoices/{invoice_id}/qr-bill.pdf", headers=auth_headers
    )
    assert resp.status_code == 200, resp.get_json()
    assert [line["text"] for line in seen["lines"]] == ["Kaffee", "Gipfeli"]
