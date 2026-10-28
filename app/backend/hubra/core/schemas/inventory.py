"""Marshmallow schemas for InventoryItem and InventoryCheckout."""

from marshmallow import EXCLUDE, RAISE, fields, validate

from hubra.core.extensions import ma
from hubra.core.models.inventory import InventoryItem

_CATEGORIES = ["Tool", "Item", "Material"]
_STATUSES = [
    "available",
    "in_use",
    "maintenance",
    "broken",
    "archived",
    "checked_out",
    "pending",
    "lost",
    "retired",
]
_VISIBILITIES = ["private", "shared"]


class InventoryItemSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = InventoryItem
        load_instance = True
        unknown = EXCLUDE
        # The guide belongs to the inventory.guides module (/guides API).
        exclude = ("instructed_members", "checkouts", "guide", "guide_url")

    cost = fields.Decimal(as_string=True, allow_none=True)
    purchase_cost = fields.Decimal(as_string=True, allow_none=True, dump_default=None)
    current_value = fields.Decimal(as_string=True, allow_none=True, dump_default=None)

    owner_name = fields.Method("get_owner_name", dump_only=True)
    responsible_name = fields.Method("get_responsible_name", dump_only=True)
    instructed_member_ids = fields.Method("get_instructed_ids", dump_only=True)
    instructed_member_names = fields.Method("get_instructed_names", dump_only=True)

    # M5 new fields
    purchase_date = fields.Date(allow_none=True, dump_default=None)
    location = fields.Str(allow_none=True, dump_default=None)
    serial_number = fields.Str(allow_none=True, dump_default=None)
    barcode_id = fields.Str(allow_none=True, dump_default=None)
    documents = fields.List(fields.Dict(), dump_default=list)
    image_url = fields.Str(allow_none=True, dump_default=None)
    notes = fields.Str(allow_none=True, dump_default=None)
    deleted_at = fields.DateTime(allow_none=True, dump_only=True, dump_default=None)

    def get_owner_name(self, obj):
        return obj.owner.name if obj.owner else None

    def get_responsible_name(self, obj):
        return obj.responsible.name if obj.responsible else None

    def get_instructed_ids(self, obj):
        return [m.id for m in (obj.instructed_members or [])]

    def get_instructed_names(self, obj):
        return [m.name for m in (obj.instructed_members or [])]


class InventoryItemCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    category = fields.Str(required=True, validate=validate.OneOf(_CATEGORIES))
    description = fields.Str(allow_none=True, load_default=None)
    owner_id = fields.Int(allow_none=True, load_default=None)
    responsible_id = fields.Int(allow_none=True, load_default=None)
    visibility = fields.Str(
        load_default="shared", validate=validate.OneOf(_VISIBILITIES)
    )
    status = fields.Str(load_default="available", validate=validate.OneOf(_STATUSES))
    cost = fields.Decimal(allow_none=True, load_default=None)
    links = fields.List(fields.Dict(), load_default=list)
    instruction_required = fields.Bool(load_default=False)
    purchase_date = fields.Date(allow_none=True, load_default=None)
    purchase_cost = fields.Decimal(allow_none=True, load_default=None)
    current_value = fields.Decimal(allow_none=True, load_default=None)
    location = fields.Str(allow_none=True, load_default=None)
    serial_number = fields.Str(allow_none=True, load_default=None)
    barcode_id = fields.Str(allow_none=True, load_default=None)
    documents = fields.List(fields.Dict(), load_default=list)
    image_url = fields.Str(allow_none=True, load_default=None)
    notes = fields.Str(allow_none=True, load_default=None)


class InventoryItemUpdateSchema(ma.Schema):
    """PATCH — all fields optional."""

    class Meta:
        unknown = RAISE

    name = fields.Str(validate=validate.Length(min=1, max=255))
    category = fields.Str(validate=validate.OneOf(_CATEGORIES))
    description = fields.Str(allow_none=True)
    owner_id = fields.Int(allow_none=True)
    responsible_id = fields.Int(allow_none=True)
    visibility = fields.Str(validate=validate.OneOf(_VISIBILITIES))
    status = fields.Str(validate=validate.OneOf(_STATUSES))
    cost = fields.Decimal(allow_none=True)
    links = fields.List(fields.Dict())
    instruction_required = fields.Bool()
    purchase_date = fields.Date(allow_none=True)
    purchase_cost = fields.Decimal(allow_none=True)
    current_value = fields.Decimal(allow_none=True)
    location = fields.Str(allow_none=True)
    serial_number = fields.Str(allow_none=True)
    barcode_id = fields.Str(allow_none=True)
    documents = fields.List(fields.Dict())
    image_url = fields.Str(allow_none=True)
    notes = fields.Str(allow_none=True)


class InventoryCheckoutSchema(ma.Schema):
    """Schema for checkout records."""

    class Meta:
        unknown = EXCLUDE

    id = fields.Int(dump_only=True)
    item_id = fields.Int(dump_only=True)
    member_id = fields.Int(dump_only=True)
    member_name = fields.Method("get_member_name", dump_only=True)
    checked_out_at = fields.DateTime(dump_only=True)
    expected_return_at = fields.DateTime(allow_none=True, dump_default=None)
    returned_at = fields.DateTime(allow_none=True, dump_only=True, dump_default=None)
    condition_notes = fields.Str(allow_none=True, dump_default=None)

    def get_member_name(self, obj):
        return obj.member.name if obj.member else None


class CheckoutCreateSchema(ma.Schema):
    """Schema for checking out an item."""

    class Meta:
        unknown = RAISE

    member_id = fields.Int(required=True)
    expected_return_at = fields.DateTime(allow_none=True, load_default=None)
    condition_notes = fields.Str(allow_none=True, load_default=None)
