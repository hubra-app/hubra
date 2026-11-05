"""StoredFile: one file a club (or a plugin of it) keeps in Hubra's file
store, in the public schema.

Only the record is here: the bytes are in the store (S3 or a local folder,
``hubra.core.files``), encrypted with the club's data key.  The record lets
the platform count a club's storage and delete a club's files with the club.
Not listed in any module manifest, so club schemas never get a copy.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class StoredFile(db.Model):
    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Who stores it: a module or plugin code, e.g. "documents".
    owner: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    content_type: Mapped[str] = mapped_column(
        String(255), nullable=False, default="application/octet-stream"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<StoredFile {self.key}>"
