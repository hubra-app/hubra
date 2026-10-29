"""The daily check that protected addresses still exist in WildDuck."""

from unittest.mock import MagicMock, patch

from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.services.wildduck import WildDuckError


def test_beat_runs_the_check_daily():
    from hubra.core.tasks import celery_app

    entry = celery_app.conf.beat_schedule["verify-protected-mail-daily"]
    assert (
        entry["task"] == "hubra.core.tasks.mail_tasks.verify_protected_mail_addresses"
    )


def test_one_broken_address_does_not_stop_the_rest_and_resync_waits_for_commit(app, db):
    from hubra.core.tasks.mail_tasks import _verify_protected_mail_addresses

    for local, wd_id in (("a", "wd-a"), ("b", "wd-b")):
        db.session.add(
            ManagedMailAddress(
                address=f"{local}@hubra.club",
                address_type="alias",
                local_part=local,
                domain="hubra.club",
                wildduck_id=wd_id,
                is_protected=True,
            )
        )
    db.session.commit()

    wd = MagicMock()
    wd.get_address.side_effect = [RuntimeError("boom"), WildDuckError(404, "gone")]
    committed = []
    with (
        patch("hubra.core.services.wildduck.try_get_client", return_value=wd),
        patch("hubra.core.tasks.wildduck.sync_managed_address.delay") as delay,
        patch.object(
            db.session, "commit", side_effect=lambda: committed.append(delay.call_count)
        ),
    ):
        result = _verify_protected_mail_addresses.__wrapped__()

    assert result["errors"] == 1 and result["re_provisioned"] == 1
    assert committed == [0]  # nothing queued before the commit
    delay.assert_called_once()
