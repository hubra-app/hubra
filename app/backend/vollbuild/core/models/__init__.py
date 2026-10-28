"""
Models package — import all models so Flask-Migrate can discover them.

Import order is significant:
  1. Global models (Tenant, Domain, User) have no inter-model FKs
     to domain models and live in the public schema.
  2. Role and MembershipTier have no inter-model FKs.
  3. Member (and its association table member_groups)
       must be imported before Group, which imports that table.
  4. All remaining models only hold FK references (resolved as strings by SA).
"""

from vollbuild.core.models.tenant import Tenant, GlobalAuditEntry
from vollbuild.core.models.domain import Domain
from vollbuild.core.models.user import User
from vollbuild.core.models.user_tenant import UserTenant
from vollbuild.core.models.tenant_request import TenantRequest
from vollbuild.core.models.role import Role, Permission, RolePermission
from vollbuild.core.models.global_role import (
    GlobalRole,
    GlobalPermission,
    GlobalRolePermission,
    UserGlobalRole,
)
from vollbuild.core.models.member import (
    Member,
    MembershipTier,
    member_groups,
    member_roles,
)
from vollbuild.core.models.application import Application
from vollbuild.core.models.group import Group, GroupMembership
from vollbuild.core.models.function import Function, FunctionHolder
from vollbuild.core.models.managed_mail import ManagedMailAddress
from vollbuild.core.models.event import ClubEvent, event_attendees, EventRegistration
from vollbuild.core.models.poll import Poll, PollOption, PollVote, PollProxy
from vollbuild.core.models.post import Post, PostLike, PostComment
from vollbuild.core.models.finance import Transaction, Invoice, TransactionCategory
from vollbuild.core.models.external_party import ExternalParty
from vollbuild.core.models.mail import MailboxFolder
from vollbuild.core.models.setting import Setting
from vollbuild.core.models.feature import Feature, TenantFeature
from vollbuild.core.models.translation import Translation
from vollbuild.core.models.notification import Notification
from vollbuild.core.models.audit import AuditEntry
from vollbuild.core.models.token import TokenBlocklist
from vollbuild.core.models.device_session import Device, Session
from vollbuild.core.models.inventory import InventoryItem, item_instructions
from vollbuild.core.models.password_reset import PasswordResetToken
from vollbuild.core.models.email_verification import EmailVerificationToken
from vollbuild.core.models.invoice_reminder import InvoiceReminderHistory
from vollbuild.core.models.code import Code
from vollbuild.core.models.internal_key import InternalKey
from vollbuild.core.models.binding import Binding
from vollbuild.core.models.backup import BackupRecord
from vollbuild.core.models.qrr_reference import QrrReference
from vollbuild.core.models.payment_plan import PaymentPlan

# Models owned by self-contained modules (vollbuild/modules/<name>/models.py).
from vollbuild.modules.finance_bank.models import BankPayment
from vollbuild.modules.finance_budgets.models import Budget, BudgetLine
from vollbuild.modules.inventory_keys.models import Key, KeyHandover

__all__ = [
    "Tenant",
    "GlobalAuditEntry",
    "Domain",
    "User",
    "UserTenant",
    "TenantRequest",
    "Role",
    "Permission",
    "RolePermission",
    "GlobalRole",
    "GlobalPermission",
    "GlobalRolePermission",
    "UserGlobalRole",
    "Member",
    "MembershipTier",
    "member_groups",
    "member_roles",
    "Application",
    "Group",
    "GroupMembership",
    "Function",
    "FunctionHolder",
    "ManagedMailAddress",
    "ClubEvent",
    "event_attendees",
    "EventRegistration",
    "Poll",
    "PollOption",
    "PollVote",
    "PollProxy",
    "Post",
    "PostLike",
    "PostComment",
    "Transaction",
    "Invoice",
    "TransactionCategory",
    "ExternalParty",
    "MailboxFolder",
    "Setting",
    "Feature",
    "TenantFeature",
    "Translation",
    "Notification",
    "AuditEntry",
    "TokenBlocklist",
    "Device",
    "Session",
    "InventoryItem",
    "item_instructions",
    "PasswordResetToken",
    "EmailVerificationToken",
    "InvoiceReminderHistory",
    "Code",
    "InternalKey",
    "Binding",
    "BackupRecord",
    "QrrReference",
    "PaymentPlan",
    "BankPayment",
    "Budget",
    "BudgetLine",
    "Key",
    "KeyHandover",
]
