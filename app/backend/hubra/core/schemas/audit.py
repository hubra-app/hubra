"""Marshmallow schemas for AuditEntry."""

from marshmallow import EXCLUDE, fields

from hubra.core.extensions import ma
from hubra.core.models.audit import AuditEntry


class AuditEntrySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AuditEntry
        load_instance = True
        unknown = EXCLUDE
        exclude = ("actor",)

    # FK column is dropped by SQLAlchemyAutoSchema when its relationship is
    # excluded; add it back explicitly so callers can filter by actorId.
    actor_id = fields.Integer(dump_only=True, allow_none=True)
    time = fields.DateTime(dump_only=True)
