"""Setting KV store model."""

from __future__ import annotations

from hubra.core.extensions import db


class Setting(db.Model):
    __tablename__ = "setting"

    key: str = db.Column(db.String(255), primary_key=True, nullable=False)
    value: str | None = db.Column(db.Text, nullable=True)
    namespace: str = db.Column(db.String(50), default="general", nullable=False)
    sensitive: bool = db.Column(db.Boolean, default=False, nullable=False)
    required: bool = db.Column(db.Boolean, default=False, nullable=False)
    restricted: bool = db.Column(db.Boolean, default=False, nullable=False)
    validation_type: str | None = db.Column(db.String(50), nullable=True)
    description: str | None = db.Column(db.Text, nullable=True)
    label: str | None = db.Column(db.String(255), nullable=True)
    is_default: bool = db.Column(db.Boolean, default=False, nullable=False)
    default_value: str | None = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        val = "****" if self.sensitive else (self.value or "")
        return f"<Setting {self.namespace}.{self.key}={val!r}>"
