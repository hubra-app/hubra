"""Celery tasks: keep the member badge's Google Wallet passes current."""

from __future__ import annotations

from hubra.core.tasks import celery_app


@celery_app.task(
    name="hubra.core.tasks.wallet_tasks.sync_google_wallet_pass",
    bind=True,
    acks_late=True,
    ignore_result=True,
)
def sync_google_wallet_pass(self, user_id: int) -> bool:
    """A failed update is not retried here: the hash stays old, so the
    nightly refresh sends it again."""
    from hubra.core.services import google_wallet

    return google_wallet.sync(user_id)


@celery_app.task(
    name="hubra.core.tasks.wallet_tasks.refresh_google_wallet_passes",
    ignore_result=True,
)
def refresh_google_wallet_passes() -> int:
    from hubra.core.services import google_wallet

    return google_wallet.refresh_all()
