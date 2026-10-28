"""Schemas package — re-exports all Marshmallow schemas."""

from hubra.core.schemas.role import RoleSchema, RoleCreateSchema
from hubra.core.schemas.member import (
    MembershipTierSchema,
    MembershipTierCreateSchema,
    MemberSchema,
    MemberCreateSchema,
    MemberUpdateSchema,
)
from hubra.core.schemas.application import (
    ApplicationSchema,
    ApplicationCreateSchema,
)
from hubra.core.schemas.group import (
    GroupSchema,
    GroupCreateSchema,
    GroupUpdateSchema,
)
from hubra.core.schemas.function import (
    FunctionSchema,
    FunctionCreateSchema,
    FunctionUpdateSchema,
    FunctionHolderSchema,
)
from hubra.core.schemas.managed_mail import ManagedMailAddressSchema
from hubra.core.schemas.event import (
    ClubEventSchema,
    ClubEventCreateSchema,
    ClubEventUpdateSchema,
)
from hubra.core.schemas.poll import (
    PollOptionSchema,
    PollSchema,
    PollCreateSchema,
    VoteSchema,
)
from hubra.core.schemas.finance import (
    TransactionCategorySchema,
    TransactionCategoryCreateSchema,
    TransactionSchema,
    TransactionCreateSchema,
    InvoiceSchema,
    InvoiceCreateSchema,
    InvoiceUpdateSchema,
)

from hubra.core.schemas.settings import SettingSchema, SettingWriteSchema
from hubra.core.schemas.code import (
    CodeSchema,
    CodeCreateSchema,
    CodeUpdateSchema,
)
from hubra.core.schemas.notification import NotificationSchema
from hubra.core.schemas.audit import AuditEntrySchema

__all__ = [
    # Role
    "RoleSchema",
    "RoleCreateSchema",
    # Membership tier
    "MembershipTierSchema",
    "MembershipTierCreateSchema",
    # Member
    "MemberSchema",
    "MemberCreateSchema",
    "MemberUpdateSchema",
    # Application
    "ApplicationSchema",
    "ApplicationCreateSchema",
    # Group
    "GroupSchema",
    "GroupCreateSchema",
    "GroupUpdateSchema",
    # Function
    "FunctionSchema",
    "FunctionCreateSchema",
    "FunctionUpdateSchema",
    "FunctionHolderSchema",
    # ManagedMailAddress
    "ManagedMailAddressSchema",
    # Event
    "ClubEventSchema",
    "ClubEventCreateSchema",
    "ClubEventUpdateSchema",
    # Poll
    "PollOptionSchema",
    "PollSchema",
    "PollCreateSchema",
    "VoteSchema",
    # Finance
    "TransactionCategorySchema",
    "TransactionCategoryCreateSchema",
    "TransactionSchema",
    "TransactionCreateSchema",
    "InvoiceSchema",
    "InvoiceCreateSchema",
    "InvoiceUpdateSchema",
    # Settings KV
    "SettingSchema",
    "SettingWriteSchema",
    # Notification
    "NotificationSchema",
    # Audit
    "AuditEntrySchema",
    # Code
    "CodeSchema",
    "CodeCreateSchema",
    "CodeUpdateSchema",
]
