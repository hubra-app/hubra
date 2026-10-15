"""Celery tasks for domain DNS verification.

Background job attempts verification every 60 seconds for 10 minutes
(10 retries total). Updates the Domain's verification_status to
'verified' or 'failed'.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone


from vollbuild.core.extensions import db
from vollbuild.core.models.domain import Domain
from vollbuild.core.services.dns_verification import verify_domain

from vollbuild.core.tasks import celery_app

_log = logging.getLogger(__name__)

_MAX_RETRIES = 10
_RETRY_DELAY = 60  # seconds


@celery_app.task(
    name="vollbuild.core.tasks.domain_tasks.verify_domain_task",
    bind=True,
    max_retries=_MAX_RETRIES,
    default_retry_delay=_RETRY_DELAY,
)
def verify_domain_task(self, domain_id: int) -> None:
    """Attempt to verify a domain's DNS TXT record.

    Retries up to _MAX_RETRIES times with _RETRY_DELAY seconds between
    attempts.  On success, marks the domain as verified.  On final
    failure, marks verification_status as 'failed'.
    """
    domain = db.session.get(Domain, domain_id)
    if domain is None:
        _log.warning("verify_domain_task: domain %d not found", domain_id)
        return

    if domain.verification_status == "verified":
        _log.info("Domain %s already verified, skipping", domain.domain)
        return

    result = verify_domain(domain.domain, domain.verification_token or "")

    if result["verified"]:
        domain.verified = True
        domain.verification_status = "verified"
        domain.verified_at = datetime.now(timezone.utc)
        db.session.commit()
        _log.info("Domain %s verified successfully", domain.domain)
    else:
        retries = self.request.retries if hasattr(self, "request") else 0
        if retries < _MAX_RETRIES - 1:
            _log.info(
                "Domain %s verification pending (attempt %d/%d): %s",
                domain.domain,
                retries + 1,
                _MAX_RETRIES,
                result.get("error", ""),
            )
            raise self.retry()
        else:
            domain.verification_status = "failed"
            db.session.commit()
            _log.warning(
                "Domain %s verification failed after %d attempts: %s",
                domain.domain,
                _MAX_RETRIES,
                result.get("error", ""),
            )
