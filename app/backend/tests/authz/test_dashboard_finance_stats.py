"""The dashboard's club money totals follow the finance overview permission."""

FINANCE = ("netMonth", "openInvoices", "openInvoicesAmount")


def test_admin_sees_finance_stats(client, auth_headers):
    stats = client.get("/api/v1/dashboard/summary").get_json()["stats"]
    assert all(stats[k] is not None for k in FINANCE)


def test_plain_member_does_not(client, plain_member_token):
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    stats = resp.get_json()["stats"]
    assert all(stats[k] is None for k in FINANCE)
    assert stats["activeMembers"] is not None


def test_treasurer_does(client, permissioned_member_factory):
    permissioned_member_factory(["finance.overview.read"])
    stats = client.get("/api/v1/dashboard/summary").get_json()["stats"]
    assert all(stats[k] is not None for k in FINANCE)
