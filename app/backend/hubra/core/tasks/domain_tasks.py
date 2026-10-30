"""Celery tasks for custom domain DNS verification.

``check_domains`` runs every minute and looks up each domain whose next
check is due:

- a new domain every minute for its first 10 minutes, then hourly until
  it is 72 hours old; after that it is 'failed' and only the club's
  "Verify" button checks it again;
- a domain nobody verified within 7 days is deleted;
- a verified domain once a week. When its record has been gone for 14
  days it stops counting as verified until the club verifies it again.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.domain import Domain
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.services.dns_verification import verify_domain

from hubra.core.tasks import celery_app

_log = logging.getLogger(__name__)

FAST_CHECKS_FOR = timedelta(minutes=10)
FAST_CHECK_EVERY = timedelta(minutes=1)
SLOW_CHECK_EVERY = timedelta(hours=1)
AUTO_CHECKS_FOR = timedelta(hours=72)
UNVERIFIED_EXPIRE_AFTER = timedelta(days=7)
RECHECK_VERIFIED_EVERY = timedelta(days=7)
RECORD_GONE_GRACE = timedelta(days=14)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _audit(action: str, domain: Domain) -> None:
    db.session.add(
        GlobalAuditEntry(
            tenant_id=domain.tenant_id,
            action=action,
            target_type="Domain",
            target_id=str(domain.id),
            details={"domain": domain.domain},
        )
    )


def _ensure_primary(tenant_id: int) -> None:
    """Give the club a verified primary domain if it has none."""
    domains = list(
        db.session.scalars(
            select(Domain)
            .where(Domain.tenant_id == tenant_id)
            .order_by(Domain.created_at)
        ).all()
    )
    if any(d.is_primary and d.verified for d in domains):
        return
    for d in domains:
        d.is_primary = False
    for d in domains:
        if d.verified:
            d.is_primary = True
            break


def check_domain(domain: Domain, now: datetime | None = None) -> dict:
    """Look up *domain*'s TXT record now and record what was found.

    The caller commits.
    """
    now = now or datetime.now(timezone.utc)
    result = verify_domain(domain.domain, domain.verification_token or "")
    domain.last_checked_at = now
    if result["verified"]:
        domain.last_seen_at = now
        if not domain.verified:
            domain.verified = True
            domain.verification_status = "verified"
            domain.verified_at = now
            db.session.flush()
            _ensure_primary(domain.tenant_id)
    elif domain.verified:
        seen = _aware(domain.last_seen_at or domain.verified_at) or now
        if now - seen > RECORD_GONE_GRACE:
            _log.warning(
                "Domain %s lost its TXT record, no longer verified", domain.domain
            )
            domain.verified = False
            domain.verification_status = "failed"
            domain.is_primary = False
            _audit("domain.unverified", domain)
            db.session.flush()
            _ensure_primary(domain.tenant_id)
    return result


def _next_check(domain: Domain, now: datetime) -> datetime | None:
    """When *domain* is next due for a check, or None for no more checks."""
    checked = _aware(domain.last_checked_at)
    if domain.verified:
        return checked + RECHECK_VERIFIED_EVERY if checked else now
    if domain.verified_at is not None:
        return None  # lost its record: the club verifies it again by hand
    age = now - _aware(domain.created_at)
    if age > AUTO_CHECKS_FOR:
        return None
    step = FAST_CHECK_EVERY if age <= FAST_CHECKS_FOR else SLOW_CHECK_EVERY
    return checked + step if checked else now


@celery_app.task(name="hubra.core.tasks.domain_tasks.check_domains")
def check_domains() -> dict:
    return _check_domains()


def _check_domains() -> dict:
    """Check every domain that is due, and expire the ones nobody verified."""
    now = datetime.now(timezone.utc)
    checked = expired = 0
    for domain in list(db.session.scalars(select(Domain)).all()):
        age = now - _aware(domain.created_at)
        if domain.verified_at is None and not domain.verified:
            if age > UNVERIFIED_EXPIRE_AFTER:
                _log.info("Domain %s never verified, removing it", domain.domain)
                _audit("domain.expired", domain)
                db.session.delete(domain)
                expired += 1
                continue
            if age > AUTO_CHECKS_FOR and domain.verification_status == "pending":
                domain.verification_status = "failed"
        due = _next_check(domain, now)
        # A little slack, so a check that ran a few seconds late still counts.
        if due is None or due > now + timedelta(seconds=5):
            continue
        try:
            check_domain(domain, now)
        except Exception:
            _log.exception("Domain check failed for %s", domain.domain)
            continue
        checked += 1
    db.session.commit()
    return {"checked": checked, "expired": expired}
