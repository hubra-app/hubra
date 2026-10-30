"""Marshmallow schemas for TransactionCategory, Transaction, Invoice, ExternalParty."""

from marshmallow import EXCLUDE, RAISE, fields, validate, validates_schema
from marshmallow.exceptions import ValidationError

from hubra.core.extensions import ma
from hubra.core.models.external_party import ExternalParty
from hubra.core.models.finance import Invoice, Transaction, TransactionCategory

_PAYMENT_METHODS = ["IBAN", "Card", "Twint", "Cash"]
_TRANSACTION_TYPES = ["income", "expense"]
_TRANSACTION_STATUSES = ["Pending", "Completed"]
_INVOICE_STATUSES = ["Paid", "Open", "Overdue"]
_INVOICE_PURPOSES = ["membership", "other"]


# ── TransactionCategory ───────────────────────────────────────────────────────


class TransactionCategorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = TransactionCategory
        load_instance = True
        unknown = EXCLUDE
        exclude = ("transactions",)


class TransactionCategoryCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    color = fields.Str(required=True, validate=validate.Regexp(r"^#[0-9A-Fa-f]{6}$"))


# ── ExternalParty ────────────────────────────────────────────────────────────


class ExternalPartySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ExternalParty
        load_instance = True
        unknown = EXCLUDE
        exclude = ("invoices",)

    created_at = fields.DateTime(format="iso")
    updated_at = fields.DateTime(format="iso")


class ExternalPartyCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    email = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=255)
    )
    address_street = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=255)
    )
    address_house_no = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=50)
    )
    address_postal_code = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=20)
    )
    address_city = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=255)
    )
    address_country = fields.Str(load_default="CH", validate=validate.Length(equal=2))
    notes = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=512)
    )


class ExternalPartyUpdateSchema(ma.Schema):
    """PATCH — all fields optional."""

    class Meta:
        unknown = RAISE

    name = fields.Str(validate=validate.Length(min=1, max=255))
    email = fields.Str(allow_none=True, validate=validate.Length(max=255))
    address_street = fields.Str(allow_none=True, validate=validate.Length(max=255))
    address_house_no = fields.Str(allow_none=True, validate=validate.Length(max=50))
    address_postal_code = fields.Str(allow_none=True, validate=validate.Length(max=20))
    address_city = fields.Str(allow_none=True, validate=validate.Length(max=255))
    address_country = fields.Str(validate=validate.Length(equal=2))
    notes = fields.Str(allow_none=True, validate=validate.Length(max=512))


# ── Transaction ───────────────────────────────────────────────────────────────


class TransactionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Transaction
        load_instance = True
        unknown = EXCLUDE
        exclude = ("category", "member", "invoice")
        include_fk = True

    date = fields.Date()
    amount = fields.Float()
    created_at = fields.DateTime(format="iso")
    invoice_id = fields.Method("get_invoice_id")
    category_name = fields.Method("get_category_name")
    member_name = fields.Method("get_member_name")

    def get_invoice_id(self, obj):
        if obj.invoice is not None:
            return obj.invoice.id
        return None

    def get_category_name(self, obj):
        if obj.category is not None:
            return obj.category.name
        return ""

    def get_member_name(self, obj):
        if obj.member is not None:
            return obj.member.name
        return ""


class TransactionCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    date = fields.Date(required=True)
    description = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    category_id = fields.Int(allow_none=True, load_default=None)
    member_id = fields.Int(allow_none=True, load_default=None)
    payee_name = fields.Str(allow_none=True, load_default=None)
    amount = fields.Float(
        required=True,
        validate=validate.Range(min=0, min_inclusive=False),
    )
    method = fields.Str(required=True, validate=validate.OneOf(_PAYMENT_METHODS))
    type = fields.Str(required=True, validate=validate.OneOf(_TRANSACTION_TYPES))


# ── Invoice ───────────────────────────────────────────────────────────────────


class TransactionUpdateSchema(ma.Schema):
    """PATCH — all fields optional."""

    class Meta:
        unknown = RAISE

    status = fields.Str(validate=validate.OneOf(_TRANSACTION_STATUSES))
    description = fields.Str(validate=validate.Length(min=1, max=255))
    date = fields.Date()
    amount = fields.Float(validate=validate.Range(min=0, min_inclusive=False))
    method = fields.Str(validate=validate.OneOf(_PAYMENT_METHODS))
    type = fields.Str(validate=validate.OneOf(_TRANSACTION_TYPES))
    category_id = fields.Int(allow_none=True)
    member_id = fields.Int(allow_none=True)
    payee_name = fields.Str(allow_none=True)


# ── Invoice ───────────────────────────────────────────────────────────────────


class InvoiceSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Invoice
        load_instance = True
        unknown = EXCLUDE
        exclude = ("member", "external_party", "transaction")
        include_fk = True

    issued = fields.Date()
    due = fields.Date()
    amount = fields.Float()
    created_at = fields.DateTime(format="iso")
    member_name = fields.Method("get_member_name")
    external_party_name = fields.Method("get_external_party_name")
    recipient_type = fields.Method("get_recipient_type")
    recipient_name = fields.Method("get_recipient_name")

    def get_member_name(self, obj):
        if obj.member is not None:
            return obj.member.name
        return ""

    def get_external_party_name(self, obj):
        if obj.external_party is not None:
            return obj.external_party.name
        return ""

    def get_recipient_type(self, obj):
        if obj.member is not None:
            return "member"
        if obj.external_party is not None:
            return "external"
        return "unknown"

    def get_recipient_name(self, obj):
        if obj.member is not None:
            return obj.member.name
        if obj.external_party is not None:
            return obj.external_party.name
        return ""


class InvoiceCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    member_id = fields.Int(allow_none=True, load_default=None)
    external_party_id = fields.Int(allow_none=True, load_default=None)
    issued = fields.Date(required=True)
    due = fields.Date(required=True)
    amount = fields.Float(
        required=True,
        validate=validate.Range(min=0, min_inclusive=False),
    )
    status = fields.Str(
        load_default="Open",
        validate=validate.OneOf(_INVOICE_STATUSES),
    )
    purpose = fields.Str(
        load_default="membership",
        validate=validate.OneOf(_INVOICE_PURPOSES),
    )
    category_id = fields.Int(allow_none=True, load_default=None)
    description = fields.Str(load_default=None, allow_none=True)

    @validates_schema
    def _validate_recipient(self, data, **kwargs):
        member_id = data.get("member_id")
        ext_id = data.get("external_party_id")
        purpose = data.get("purpose", "membership")

        if member_id is None and ext_id is None:
            raise ValidationError("Either member_id or external_party_id is required.")
        if member_id is not None and ext_id is not None:
            raise ValidationError(
                "member_id and external_party_id are mutually exclusive."
            )
        if purpose == "membership" and member_id is None:
            raise ValidationError(
                "purpose='membership' requires a member_id recipient."
            )

    @validates_schema
    def _validate_dates(self, data, **kwargs):
        if data.get("due") and data.get("issued") and data["due"] < data["issued"]:
            raise ValidationError("due is before issued", "due")


class InvoiceUpdateSchema(ma.Schema):
    """PATCH — all fields optional."""

    class Meta:
        unknown = RAISE

    member_id = fields.Int(allow_none=True)
    external_party_id = fields.Int(allow_none=True)
    issued = fields.Date()
    due = fields.Date()
    amount = fields.Float(validate=validate.Range(min=0, min_inclusive=False))
    status = fields.Str(validate=validate.OneOf(_INVOICE_STATUSES))
    purpose = fields.Str(validate=validate.OneOf(_INVOICE_PURPOSES))
    category_id = fields.Int(allow_none=True)
    description = fields.Str(allow_none=True)
