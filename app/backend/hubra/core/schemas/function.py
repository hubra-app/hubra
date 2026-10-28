"""Marshmallow schemas for Function and FunctionHolder."""

from marshmallow import EXCLUDE, fields, validate

from hubra.core.extensions import ma
from hubra.core.models.function import Function, FunctionHolder


class FunctionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Function
        load_instance = True
        unknown = EXCLUDE
        exclude = ("holders",)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class FunctionCreateSchema(ma.Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True, load_default=None)
    max_holders = fields.Int(load_default=1, validate=validate.Range(min=1))


class FunctionUpdateSchema(ma.Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    max_holders = fields.Int(validate=validate.Range(min=1))


class FunctionHolderSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = FunctionHolder
        load_instance = True
        unknown = EXCLUDE
        exclude = ("function",)

    member = fields.Method("get_member_stub", dump_only=True)

    def get_member_stub(self, obj):
        m = obj.member
        return {"id": m.id, "name": m.name} if m else None
