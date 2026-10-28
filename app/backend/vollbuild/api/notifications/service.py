from datetime import datetime, timezone

from vollbuild.extensions import db
from vollbuild.core.models.notification import Notification


def create_notification(
    member_id: int,
    kind: str = "info",
    title: str = "",
    msg: str = "",
) -> Notification:
    notif = Notification(
        member_id=member_id,
        kind=kind,
        title=title,
        msg=msg,
        time=datetime.now(timezone.utc),
        read=False,
    )
    db.session.add(notif)
    db.session.flush()
    return notif
