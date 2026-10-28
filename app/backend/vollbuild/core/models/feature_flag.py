"""FeatureFlag model — runtime feature toggles stored in the DB."""

from __future__ import annotations

from vollbuild.extensions import db


class FeatureFlag(db.Model):
    __tablename__ = "feature_flag"

    key: str = db.Column(db.String(50), primary_key=True, nullable=False)
    enabled: bool = db.Column(db.Boolean, default=False, nullable=False)
    label: str | None = db.Column(db.String(255), nullable=True)
    description: str | None = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<FeatureFlag {self.key}={self.enabled}>"
