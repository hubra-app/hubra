"""Code schemas — Marshmallow serialization/validation."""

from __future__ import annotations

from marshmallow import EXCLUDE, RAISE, Schema, fields, validate

from hubra.core.extensions import ma
from hubra.core.models.code import Code


class CodeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Code
        load_instance = True
        unknown = EXCLUDE
        exclude = ("created_by_id", "updated_by_id")

    code = fields.Method("get_plain_code", dump_only=True)
    created_by = fields.Method("get_created_by", dump_only=True)
    updated_by = fields.Method("get_updated_by", dump_only=True)

    @staticmethod
    def get_plain_code(obj: Code) -> str:
        return obj.plain_code

    @staticmethod
    def get_created_by(obj: Code) -> str | None:
        return obj.created_by.name if obj.created_by else None

    @staticmethod
    def get_updated_by(obj: Code) -> str | None:
        return obj.updated_by.name if obj.updated_by else None


class CodeCreateSchema(Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    code = fields.Str(required=True, validate=validate.Length(min=1))
    description = fields.Str(load_default=None, allow_none=True)


class CodeUpdateSchema(Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(validate=validate.Length(min=1, max=255))
    code = fields.Str(validate=validate.Length(min=1))
    description = fields.Str(allow_none=True)
    is_active = fields.Bool()
