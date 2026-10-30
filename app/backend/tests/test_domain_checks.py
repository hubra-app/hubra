"""Custom domains are checked on their own, re-checked, and expire.

DNS is mocked: ``_records`` maps a name to the TXT strings published on it.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import dns.resolver
import pytest

from hubra.core.models.domain import Domain
from hubra.core.models.tenant import Tenant
from hubra.core.services.dns_verification import verify_domain
from hubra.core.tasks.domain_tasks import _check_domains as check_domains

NOW = datetime.now(timezone.utc)


def _resolver(records: dict[str, list[str]]):
    def resolve(name, _rtype):
        if name not in records:
            raise dns.resolver.NXDOMAIN()
        answers = []
        for value in records[name]:
            answer = MagicMock()
            answer.strings = [value.encode()]
            answers.append(answer)
        return answers

    resolver = MagicMock()
    resolver.resolve.side_effect = resolve
    return patch("dns.resolver.Resolver", return_value=resolver)


@pytest.fixture
def tenant(db, seeded_db):
    tenant = Tenant(name="Domain Club", slug="domain-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    return tenant


def _domain(db, tenant, name="fcx.ch", **fields):
    domain = Domain(
        tenant_id=tenant.id,
        domain=name,
        verification_token="tok",
        verification_status=fields.pop("verification_status", "pending"),
        **fields,
    )
    db.session.add(domain)
    db.session.commit()
    return domain


# ── Where the record is looked up ───────────────────────────────────────────


def test_record_on_its_own_label_verifies():
    with _resolver({"_hubra-verify.members.fcx.ch": ["hubra-verify=tok"]}):
        assert verify_domain("members.fcx.ch", "tok")["verified"] is True


def test_record_on_the_domain_itself_still_verifies():
    with _resolver({"fcx.ch": ["v=spf1 -all", "hubra-verify=tok"]}):
        assert verify_domain("fcx.ch", "tok")["verified"] is True


def test_long_record_split_into_chunks_verifies():
    answer = MagicMock()
    answer.strings = [b"hubra-ver", b"ify=tok"]
    resolver = MagicMock()
    resolver.resolve.return_value = [answer]
    with patch("dns.resolver.Resolver", return_value=resolver):
        assert verify_domain("fcx.ch", "tok")["verified"] is True


def test_no_record_reports_why():
    with _resolver({}):
        result = verify_domain("fcx.ch", "tok")
    assert result["verified"] is False
    assert "NXDOMAIN" in result["error"]


# ── The periodic check ──────────────────────────────────────────────────────


def test_new_domain_is_checked_and_becomes_primary(db, tenant):
    domain = _domain(db, tenant)
    with _resolver({"_hubra-verify.fcx.ch": ["hubra-verify=tok"]}):
        assert check_domains()["checked"] == 1
    db.session.refresh(domain)
    assert domain.verified is True
    assert domain.verification_status == "verified"
    assert domain.is_primary is True
    assert domain.last_seen_at is not None


def test_second_verified_domain_does_not_take_primary(db, tenant):
    first = _domain(
        db, tenant, "first.ch", verified=True, verification_status="verified",
        verified_at=NOW, last_checked_at=NOW, is_primary=True,
    )
    second = _domain(db, tenant, "second.ch")
    with _resolver({"_hubra-verify.second.ch": ["hubra-verify=tok"]}):
        check_domains()
    db.session.refresh(first)
    db.session.refresh(second)
    assert second.verified is True
    assert (first.is_primary, second.is_primary) == (True, False)


def test_domain_not_due_is_not_looked_up(db, tenant):
    _domain(db, tenant, created_at=NOW - timedelta(hours=1), last_checked_at=NOW)
    with _resolver({}):
        assert check_domains()["checked"] == 0


def test_unverified_after_72_hours_is_failed_and_no_longer_checked(db, tenant):
    domain = _domain(db, tenant, created_at=NOW - timedelta(hours=73))
    with _resolver({"_hubra-verify.fcx.ch": ["hubra-verify=tok"]}):
        assert check_domains()["checked"] == 0
    db.session.refresh(domain)
    assert domain.verification_status == "failed"
    assert domain.verified is False


def test_unverified_after_7_days_is_removed(db, tenant):
    domain = _domain(db, tenant, created_at=NOW - timedelta(days=8))
    did = domain.id
    with _resolver({}):
        assert check_domains()["expired"] == 1
    assert db.session.get(Domain, did) is None


def test_verified_domain_keeps_its_status_while_the_record_is_briefly_gone(
    db, tenant
):
    domain = _domain(
        db, tenant, verified=True, verification_status="verified",
        verified_at=NOW - timedelta(days=30), last_seen_at=NOW - timedelta(days=8),
        last_checked_at=NOW - timedelta(days=8), is_primary=True,
        created_at=NOW - timedelta(days=30),
    )
    with _resolver({}):
        assert check_domains()["checked"] == 1
    db.session.refresh(domain)
    assert domain.verified is True
    assert domain.is_primary is True


def test_verified_domain_without_record_for_14_days_is_unverified(db, tenant):
    domain = _domain(
        db, tenant, verified=True, verification_status="verified",
        verified_at=NOW - timedelta(days=60), last_seen_at=NOW - timedelta(days=15),
        last_checked_at=NOW - timedelta(days=8), is_primary=True,
        created_at=NOW - timedelta(days=60),
    )
    did = domain.id
    with _resolver({}):
        check_domains()
    domain = db.session.get(Domain, did)
    assert domain.verified is False
    assert domain.verification_status == "failed"
    assert domain.is_primary is False
    # It is kept so the club can put the record back and verify again.
    with _resolver({}):
        assert check_domains() == {"checked": 0, "expired": 0}
    assert db.session.get(Domain, did) is not None


# ── The club's mail domain ──────────────────────────────────────────────────


def _put_mail_domain(client, value):
    return client.put("/api/v1/settings/mail.domain", json={"value": value})


def test_mail_domain_must_be_verified(client, auth_headers):
    resp = _put_mail_domain(client, "fcx.ch")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "DOMAIN_NOT_VERIFIED"


def test_platform_mail_domain_needs_no_proof(client, auth_headers, app):
    platform = app.config.get("MAIL_DOMAIN") or "hubra.club"
    assert _put_mail_domain(client, f"fcx.{platform}").status_code == 200


def test_verified_domain_can_be_the_mail_domain(client, auth_headers, db, tenant):
    _domain(db, tenant, verified=True, verification_status="verified")
    with patch("hubra.core.tenant.context.current_tenant", return_value=tenant):
        assert _put_mail_domain(client, "fcx.ch").status_code == 200
