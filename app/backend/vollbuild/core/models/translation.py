"""Translation model for backend-driven i18n."""

from __future__ import annotations

from datetime import datetime, timezone

from vollbuild.core.extensions import db


class Translation(db.Model):
    __tablename__ = "translation"
    __table_args__ = (db.UniqueConstraint("locale", "key"),)

    id: int = db.Column(db.Integer, primary_key=True)
    locale: str = db.Column(db.String(10), nullable=False, index=True)
    key: str = db.Column(db.String(255), nullable=False)
    value: str = db.Column(db.Text, nullable=False)
    default_value: str | None = db.Column(db.Text, nullable=True)
    needs_attention: bool = db.Column(db.Boolean, default=False, nullable=False)
    is_missing: bool = db.Column(db.Boolean, default=False, nullable=False)
    last_used_at: datetime | None = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at: datetime = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_by_id: int | None = db.Column(
        db.Integer, db.ForeignKey("members.id"), nullable=True
    )
    alias_for: str | None = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Translation {self.locale}.{self.key}>"
