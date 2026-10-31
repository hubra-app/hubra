"""DataKey: the keys that encrypt stored secrets, one set per club.

Public schema only (no module manifest lists it, so club schemas never get
a copy).  Each club (``scope`` ``c<tenant id>``) and the platform (``p``)
has its own random 256-bit key; ``wrapped_key`` is that key encrypted with
the master key (``FERNET_KEY``), so rotating the master key only rewraps
these rows.  A new ``version`` takes over for new values; older versions
stay to open older values and backups.  Deleting a club for good deletes
its rows (``TenantService.delete_tenant``), which makes its stored secrets
unreadable everywhere, backups included.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class DataKey(db.Model):
    __tablename__ = "data_keys"
    __table_args__ = (
        UniqueConstraint("scope", "version", name="uq_data_keys_scope_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    wrapped_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<DataKey {self.scope} v{self.version}>"
