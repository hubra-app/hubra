"""TokenBlocklist model — JWT token revocation for flask-jwt-extended 4.x."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    # JWT ID claim — used by flask-jwt-extended token_in_blocklist_loader
    jti: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    # access | refresh
    type: Mapped[str] = mapped_column(db.String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TokenBlocklist id={self.id} jti={self.jti!r} type={self.type!r}>"
