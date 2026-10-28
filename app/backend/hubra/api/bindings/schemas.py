"""Marshmallow schemas for InternalKey and Binding serialization."""

from __future__ import annotations

from marshmallow import fields, Schema


class InternalKeyCreateSchema(Schema):
    key = fields.String(required=True)
    allow_multiple = fields.Boolean(load_default=False)
    is_protected = fields.Boolean(load_default=False)
    label = fields.String(allow_none=True, load_default=None)


class InternalKeyUpdateSchema(Schema):
    label = fields.String(allow_none=True)
    allow_multiple = fields.Boolean(allow_none=True)
    is_protected = fields.Boolean(allow_none=True)


class BindingCreateSchema(Schema):
    type = fields.String(required=True)
    source_id = fields.String(required=True)
    source_attribute = fields.String(required=True)
    key_id = fields.Integer(required=True)
    validator = fields.String(load_default="none")
    enabled = fields.Boolean(load_default=True)
    is_protected = fields.Boolean(load_default=False)


class BindingUpdateSchema(Schema):
    type = fields.String(allow_none=True)
    source_id = fields.String(allow_none=True)
    source_attribute = fields.String(allow_none=True)
    key_id = fields.Integer(allow_none=True)
    validator = fields.String(allow_none=True)
    enabled = fields.Boolean(allow_none=True)
    is_protected = fields.Boolean(allow_none=True)


class BindingToggleSchema(Schema):
    enabled = fields.Boolean(required=True)
