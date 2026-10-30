"""Marshmallow schemas for MembershipTier and Member.

Member is a thin link table — identity fields (name, email, password, etc.)
live on User and are exposed via passthrough properties on Member. The
MemberSchema includes these as Method fields so the serialized output
shape stays compatible with the frontend.
"""

import marshmallow
from marshmallow import EXCLUDE, RAISE, fields, validate

from hubra.core.extensions import ma
from hubra.core.models.member import Member, MembershipTier


# ── MembershipTier ────────────────────────────────────────────────────────────


class MembershipTierSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = MembershipTier
        load_instance = True
        unknown = EXCLUDE
        exclude = ("members", "applications")

    # Serialize Decimal as float for JSON
    price_chf = fields.Float(allow_none=True, dump_default=None)
    percentage_value = fields.Float(allow_none=True, dump_default=None)
    coefficient = fields.Float(allow_none=True, dump_default=None)
    round_to = fields.Int(allow_none=True, dump_default=None)
    deduct_tier_ids = fields.List(fields.Int(), allow_none=True, dump_default=None)
    payment_plans = fields.Method("get_payment_plans", dump_only=True)

    def get_payment_plans(self, obj):
        from hubra.api.tiers.plans import plan_to_dict

        return [plan_to_dict(p) for p in obj.payment_plans]

    def dump(self, obj, *, many=None):
        result = super().dump(obj, many=many)
        if isinstance(result, list):
            for item in result:
                if item.get("deduct_tier_ids") is None:
                    item["deduct_tier_ids"] = []
        else:
            if result.get("deduct_tier_ids") is None:
                result["deduct_tier_ids"] = []
        return result


class MembershipTierCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    price_chf = fields.Float(
        required=False,
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=0, min_inclusive=False),
    )
    color = fields.Str(required=True, validate=validate.Regexp(r"^#[0-9A-Fa-f]{6}$"))
    billing_cycle = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.OneOf(["monthly", "yearly"]),
    )
    price_type = fields.Str(
        required=True,
        validate=validate.OneOf(["fixed", "percentage", "formula"]),
    )
    percentage_value = fields.Float(
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0),
    )
    coefficient = fields.Float(allow_none=True, load_default=None)
    round_to = fields.Int(allow_none=True, load_default=None)
    deduct_tier_ids = fields.List(fields.Int(), load_default=[])


# ── Nested stubs (used inside MemberSchema) ───────────────────────────────────


class _TierStubSchema(ma.Schema):
    id = fields.Int()
    name = fields.Str()
    price_chf = fields.Float(allow_none=True)
    color = fields.Str(allow_none=True)
    billing_cycle = fields.Str(allow_none=True)
    price_type = fields.Str(allow_none=True)
    percentage_value = fields.Float(allow_none=True)
    coefficient = fields.Float(allow_none=True)
    round_to = fields.Int(allow_none=True)
    deduct_tier_ids = fields.List(fields.Int(), allow_none=True)


class _RoleStubSchema(ma.Schema):
    id = fields.Int()
    name = fields.Str()


# ── MemberSchema ──────────────────────────────────────────────────────────────


class MemberSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Member
        load_instance = True
        unknown = EXCLUDE
        exclude = ("led_groups", "events")

    # Identity fields — now passthrough properties on Member reading from User
    name = fields.Method("get_name", dump_only=True)
    email = fields.Method("get_email", dump_only=True)
    first_name = fields.Method("get_first_name", dump_only=True)
    last_name = fields.Method("get_last_name", dump_only=True)
    avatar = fields.Method("get_avatar", dump_only=True, allow_none=True)
    avatar_color = fields.Method("get_avatar_color", dump_only=True)
    must_change_password = fields.Method("get_must_change_password", dump_only=True)
    is_disabled = fields.Method("get_is_disabled", dump_only=True)
    private_email_verified = fields.Method("get_private_email_verified", dump_only=True)
    language = fields.Method("get_language", dump_only=True)
    phone = fields.Method("get_phone", dump_only=True, allow_none=True)
    mobile = fields.Method("get_mobile", dump_only=True, allow_none=True)
    birthday = fields.Method("get_birthday", dump_only=True, allow_none=True)
    profile_note = fields.Method("get_profile_note", dump_only=True, allow_none=True)
    last_seen = fields.Method("get_last_seen", dump_only=True, allow_none=True)

    # Address fields (read from User)
    address_street = fields.Method(
        "get_address_street", dump_only=True, allow_none=True
    )
    address_house_no = fields.Method(
        "get_address_house_no", dump_only=True, allow_none=True
    )
    address_postal_code = fields.Method(
        "get_address_postal_code", dump_only=True, allow_none=True
    )
    address_city = fields.Method("get_address_city", dump_only=True, allow_none=True)
    address_country = fields.Method("get_address_country", dump_only=True)

    # Emergency contact (read from User)
    emergency_contact = fields.Method(
        "get_emergency_contact", dump_only=True, allow_none=True
    )

    # Nested read-only relationships
    tier = fields.Nested(_TierStubSchema, dump_only=True, allow_none=True)
    roles = fields.List(fields.Nested(_RoleStubSchema), dump_only=True, dump_default=[])

    # Computed list fields from M:N relationships
    group_ids = fields.Method("get_group_ids", dump_only=True)

    # Typed date/datetime serialisation
    joined = fields.Date(allow_none=True)
    deleted_at = fields.DateTime(allow_none=True, dump_only=True, dump_default=None)

    # Club username (unique per tenant, admin-editable)
    club_username = fields.Str(dump_default=None, allow_none=True)

    # Tenant-specific fields
    membership_type = fields.Str(dump_default="regular")
    membership_until = fields.Date(allow_none=True, dump_default=None)
    custom_fields = fields.Dict(allow_none=True, dump_default=None)
    directory_shared = fields.Method("get_directory_shared", dump_only=True)

    def get_directory_shared(self, obj):
        return list(obj.directory_shared or [])

    def get_name(self, obj):
        return obj.name

    def get_email(self, obj):
        return obj.email

    def get_first_name(self, obj):
        return obj.first_name

    def get_last_name(self, obj):
        return obj.last_name

    def get_avatar(self, obj):
        return obj.avatar

    def get_avatar_color(self, obj):
        return obj.avatar_color

    def get_must_change_password(self, obj):
        return obj.must_change_password

    def get_is_disabled(self, obj):
        return obj.is_disabled

    def get_private_email_verified(self, obj):
        return obj.private_email_verified

    def get_language(self, obj):
        return obj.language

    def get_phone(self, obj):
        return obj.phone

    def get_mobile(self, obj):
        return obj.mobile

    def get_birthday(self, obj):
        return obj.birthday.isoformat() if obj.birthday else None

    def get_profile_note(self, obj):
        return obj.profile_note

    def get_last_seen(self, obj):
        return obj.last_seen.isoformat() if obj.last_seen else None

    def get_address_street(self, obj):
        return obj.user.address_street if obj.user else None

    def get_address_house_no(self, obj):
        return obj.user.address_house_no if obj.user else None

    def get_address_postal_code(self, obj):
        return obj.user.address_postal_code if obj.user else None

    def get_address_city(self, obj):
        return obj.user.address_city if obj.user else None

    def get_address_country(self, obj):
        return obj.user.address_country if obj.user else "CH"

    def get_emergency_contact(self, obj):
        return obj.user.emergency_contact if obj.user else None

    def get_group_ids(self, obj):
        return [g.id for g in (obj.groups or [])]


# ── MemberCreateSchema ────────────────────────────────────────────────────────


class MemberCreateSchema(ma.Schema):
    """Create a Member linked to an existing User, or create both.

    If user_id is provided, identity fields are read from the User.
    If not, first_name/last_name/email are required to create a new User.
    """

    class Meta:
        unknown = RAISE

    user_id = fields.Int(load_default=None, allow_none=True)
    first_name = fields.Str(required=False, validate=validate.Length(min=1, max=255))
    last_name = fields.Str(required=False, validate=validate.Length(min=1, max=255))
    email = fields.Email(required=False)
    password = fields.Str(load_default=None, allow_none=True)

    # User-level identity fields (applied to the User during creation)
    phone = fields.Str(allow_none=True, load_default=None)
    mobile = fields.Str(allow_none=True, load_default=None)
    birthday = fields.Date(allow_none=True, load_default=None)
    address_street = fields.Str(allow_none=True, load_default=None)
    address_house_no = fields.Str(allow_none=True, load_default=None)
    address_postal_code = fields.Str(allow_none=True, load_default=None)
    address_city = fields.Str(allow_none=True, load_default=None)
    address_country = fields.Str(allow_none=True, load_default=None)
    emergency_contact = fields.Dict(allow_none=True, load_default=None)

    tier_id = fields.Int(load_default=None, allow_none=True)
    role_ids = fields.List(fields.Int(), load_default=[])
    status = fields.Str(
        load_default="trial",
        validate=validate.OneOf(["active", "trial", "inactive", "suspended"]),
    )
    group_ids = fields.List(fields.Int(), load_default=[])
    tool_hours = fields.Int(load_default=0, validate=validate.Range(min=0))
    notes = fields.Str(allow_none=True, load_default=None)
    joined = fields.Date(allow_none=True, load_default=None)
    membership_type = fields.Str(
        load_default="regular",
        validate=validate.OneOf(["regular", "honorary", "passive", "trial"]),
    )
    membership_until = fields.Date(allow_none=True, load_default=None)
    custom_fields = fields.Dict(allow_none=True, load_default=None)


# ── MemberUpdateSchema ────────────────────────────────────────────────────────


class MemberUpdateSchema(ma.Schema):
    """PATCH — every field is optional.

    Identity fields (first_name, last_name, email, etc.) are proxied to
    the linked User by the service layer. Tenant-specific fields are
    updated directly on the Member.
    """

    class Meta:
        unknown = RAISE

    # Identity fields (proxied to User by service layer)
    first_name = fields.Str(validate=validate.Length(min=1, max=255))
    last_name = fields.Str(validate=validate.Length(min=1, max=255))
    email = fields.Email()
    avatar_color = fields.Str(validate=validate.Regexp(r"^#[0-9A-Fa-f]{6}$"))
    must_change_password = fields.Bool()
    phone = fields.Str(allow_none=True)
    mobile = fields.Str(allow_none=True)
    birthday = fields.Date(allow_none=True)
    address_street = fields.Str(allow_none=True)
    address_house_no = fields.Str(allow_none=True)
    address_postal_code = fields.Str(allow_none=True)
    address_city = fields.Str(allow_none=True)
    address_country = fields.Str(validate=validate.Length(min=2, max=2))
    emergency_contact = fields.Dict(allow_none=True)

    # Tenant-specific fields
    tier_id = fields.Int(allow_none=True)
    role_ids = fields.List(fields.Int(), allow_none=True)
    status = fields.Str(
        validate=validate.OneOf(["active", "trial", "inactive", "suspended"])
    )
    group_ids = fields.List(fields.Int())
    tool_hours = fields.Int(
        load_default=marshmallow.missing, validate=validate.Range(min=0)
    )
    notes = fields.Str(allow_none=True)
    joined = fields.Date(allow_none=True)
    club_username = fields.Str(allow_none=True, validate=validate.Length(min=1, max=64))
    forwarding_enabled = fields.Bool()
    retention_days = fields.Int(allow_none=True, validate=validate.Range(min=1))
    membership_type = fields.Str(
        validate=validate.OneOf(["regular", "honorary", "passive", "trial"])
    )
    membership_until = fields.Date(allow_none=True)
    custom_fields = fields.Dict(allow_none=True)
