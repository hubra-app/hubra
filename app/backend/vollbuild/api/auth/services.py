"""Auth & Account service — login, password reset, bootstrap, account management."""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from sqlalchemy import select

from vollbuild.core.errors import raise_error
from vollbuild.core.extensions import db
from vollbuild.core.models.audit import AuditEntry
from vollbuild.core.models.finance import Invoice
from vollbuild.core.models.member import Member
from vollbuild.core.models.email_verification import EmailVerificationToken
from vollbuild.core.models.password_reset import PasswordResetToken
from vollbuild.core.models.token import TokenBlocklist
from vollbuild.core.models.user import User
from vollbuild.core.models.user_tenant import UserTenant
from vollbuild.core.models.device_session import Device, Session
from vollbuild.core.tenant.context import current_tenant

_EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")
_log = logging.getLogger(__name__)

_MIN_PASSWORD_LEN = 12
_MIN_ZXCVBN_SCORE = 3  # 0-4; 3 = "safely unguessable"

_UA_RE = re.compile(r"(Chrome|Firefox|Safari|Edge|Opera)/(\d+)", re.IGNORECASE)
_OS_RE = re.compile(
    r"(Windows NT [\d.]+|Mac OS X [\d_]+|Android [\d.]+|iPhone OS [\d_]+|Linux)",
    re.IGNORECASE,
)


def _extract_browser_family(headers) -> str:
    """Extract stable browser family (Chrome/Firefox/Safari/Edge/Opera)."""
    sec_ch_ua = headers.get("Sec-CH-UA", "") or ""
    if sec_ch_ua:
        for brand in ("Chrome", "Edge", "Opera", "Firefox", "Safari"):
            if brand in sec_ch_ua:
                return brand
    ua = headers.get("User-Agent", "") or ""
    for pattern, family in [
        (_UA_RE, None),
    ]:
        m = pattern.search(ua)
        if m:
            return m.group(1).capitalize()
    if "Firefox" in ua:
        return "Firefox"
    if "Safari" in ua and "Chrome" not in ua:
        return "Safari"
    return "Unknown"


def _extract_platform(headers) -> str:
    """Extract stable platform family (Windows/macOS/Linux/Android/iOS)."""
    sec_ch_ua_platform = headers.get("Sec-CH-UA-Platform", "") or ""
    if sec_ch_ua_platform:
        return sec_ch_ua_platform.strip('"')
    ua = headers.get("User-Agent", "") or ""
    if "Windows" in ua:
        return "Windows"
    if "Mac OS" in ua or "Macintosh" in ua:
        return "macOS"
    if "Android" in ua:
        return "Android"
    if "iPhone" in ua or "iPad" in ua:
        return "iOS"
    if "Linux" in ua:
        return "Linux"
    return "Unknown"


def compute_fingerprint(headers) -> str:
    """Compute a stable SHA-256 fingerprint from browser request headers.

    Uses only stable, low-entropy components:
    - Browser family (Chrome/Firefox/Safari/Edge) — no version numbers
    - Platform family (Windows/macOS/Linux/Android/iOS) — no version numbers
    - Mobile flag (Sec-CH-UA-Mobile)

    High-entropy Client Hints and version numbers are intentionally excluded
    because they change with browser updates and are absent on first request
    before Accept-CH is cached.
    """
    browser = _extract_browser_family(headers)
    platform = _extract_platform(headers)
    mobile = headers.get("Sec-CH-UA-Mobile", "") or ""

    raw = f"browser:{browser}|platform:{platform}|mobile:{mobile}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _enforce_password_strength(password: str) -> None:
    """Raise 400 if password is shorter than 12 chars or has zxcvbn score < 3."""
    if len(password) < _MIN_PASSWORD_LEN:
        raise_error(
            400,
            "WEAK_PASSWORD",
            f"Password must be at least {_MIN_PASSWORD_LEN} characters",
        )
    import zxcvbn as _zxcvbn

    result = _zxcvbn.zxcvbn(password)
    if result["score"] < _MIN_ZXCVBN_SCORE:
        feedback = result.get("feedback", {})
        warning = feedback.get("warning") or "Password is too weak"
        raise_error(400, "WEAK_PASSWORD", warning)


# SVG tags that are safe to preserve in user-uploaded avatars.
# Omits <script>, <foreignObject>, <embed>, <object>, <animate*> (event triggers).
_SVG_ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "svg",
        "g",
        "defs",
        "title",
        "desc",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "text",
        "tspan",
        "textPath",
        "use",
        "symbol",
        "linearGradient",
        "radialGradient",
        "stop",
        "clipPath",
        "mask",
        "filter",
        "feBlend",
        "feColorMatrix",
        "feComponentTransfer",
        "feComposite",
        "feConvolveMatrix",
        "feDiffuseLighting",
        "feDisplacementMap",
        "feFlood",
        "feGaussianBlur",
        "feImage",
        "feMerge",
        "feMergeNode",
        "feMorphology",
        "feOffset",
        "feSpecularLighting",
        "feTile",
        "feTurbulence",
        "feFuncA",
        "feFuncB",
        "feFuncG",
        "feFuncR",
        "feDistantLight",
        "fePointLight",
        "feSpotLight",
        "image",
    }
)
# Presentation and structural attributes that are safe per-tag.
# Event handlers (on*) and javascript: URIs are stripped by nh3 automatically
# when they do not appear in this allowlist.
_SVG_ALLOWED_ATTRS: dict[str, set[str]] = {
    "svg": {"viewBox", "xmlns", "width", "height", "version"},
    "path": {
        "d",
        "fill",
        "stroke",
        "stroke-width",
        "fill-rule",
        "clip-rule",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "opacity",
        "fill-opacity",
        "stroke-opacity",
        "transform",
    },
    "rect": {
        "x",
        "y",
        "width",
        "height",
        "rx",
        "ry",
        "fill",
        "stroke",
        "stroke-width",
        "opacity",
        "fill-opacity",
        "transform",
    },
    "circle": {
        "cx",
        "cy",
        "r",
        "fill",
        "stroke",
        "stroke-width",
        "opacity",
        "fill-opacity",
        "transform",
    },
    "ellipse": {
        "cx",
        "cy",
        "rx",
        "ry",
        "fill",
        "stroke",
        "stroke-width",
        "opacity",
        "fill-opacity",
        "transform",
    },
    "line": {
        "x1",
        "y1",
        "x2",
        "y2",
        "stroke",
        "stroke-width",
        "opacity",
        "stroke-opacity",
        "transform",
    },
    "polyline": {
        "points",
        "fill",
        "stroke",
        "stroke-width",
        "opacity",
        "fill-opacity",
        "transform",
    },
    "polygon": {
        "points",
        "fill",
        "stroke",
        "stroke-width",
        "opacity",
        "fill-opacity",
        "transform",
    },
    "g": {"transform", "opacity", "fill", "stroke", "clip-path", "mask", "id"},
    "text": {
        "x",
        "y",
        "dx",
        "dy",
        "text-anchor",
        "font-family",
        "font-size",
        "font-weight",
        "fill",
        "opacity",
        "transform",
    },
    "tspan": {
        "x",
        "y",
        "dx",
        "dy",
        "font-family",
        "font-size",
        "font-weight",
        "fill",
    },
    "use": {"href", "x", "y", "width", "height", "transform"},
    "image": {"href", "x", "y", "width", "height", "transform", "preserveAspectRatio"},
    "linearGradient": {
        "id",
        "x1",
        "y1",
        "x2",
        "y2",
        "gradientUnits",
        "gradientTransform",
    },
    "radialGradient": {
        "id",
        "cx",
        "cy",
        "r",
        "fx",
        "fy",
        "gradientUnits",
        "gradientTransform",
    },
    "stop": {"offset", "stop-color", "stop-opacity"},
    "clipPath": {"id", "clipPathUnits"},
    "mask": {"id", "maskUnits", "x", "y", "width", "height"},
    "defs": {"id"},
    "symbol": {"id", "viewBox", "width", "height"},
    "filter": {
        "id",
        "x",
        "y",
        "width",
        "height",
        "color-interpolation-filters",
    },
}


def _sanitize_svg_avatar(value: str | None) -> str | None:
    """Sanitize SVG data URI avatars, stripping script elements, event handlers,
    javascript: URIs, and foreignObject. Non-SVG values pass through unchanged."""
    if value is None or not isinstance(value, str):
        return value
    if not value.startswith("data:image/svg+xml"):
        return value

    import nh3

    _, sep, data = value.partition(",")
    if not sep:
        raise_error(400, "VALIDATION_ERROR", "Invalid SVG avatar data URI")

    prefix = value[: value.index(",")]
    if "base64" in prefix:
        try:
            svg_str = base64.b64decode(data).decode("utf-8")
        except Exception:
            raise_error(400, "VALIDATION_ERROR", "Invalid base64 SVG avatar")
    else:
        svg_str = unquote(data)

    clean = nh3.clean(
        svg_str,
        tags=_SVG_ALLOWED_TAGS,
        attributes=_SVG_ALLOWED_ATTRS,
        strip_comments=True,
        link_rel=None,
    )

    clean_b64 = base64.b64encode(clean.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{clean_b64}"


class AuthService:
    """Authentication business logic."""

    @staticmethod
    def authenticate(email: str, password: str) -> Member:
        """Find a member by email, verify password, handle lockout."""
        if not email or not password:
            raise_error(401, "UNAUTHORIZED", "Invalid credentials")

        member = db.session.scalar(
            select(Member)
            .join(User, Member.user_id == User.id)
            .where((User.email == email) | (Member.public_email == email))
            .where(Member.archived_at.is_(None))
        )

        if member is None:
            raise_error(401, "UNAUTHORIZED", "Invalid credentials")

        if member.is_disabled:
            _log.warning(
                "Disabled account login attempt",
                extra={"member_id": member.id, "is_disabled": True},
            )
            raise_error(
                403, "ACCOUNT_DISABLED", "Account has been disabled by an administrator"
            )

        _locked_until = member.locked_until
        if _locked_until is not None and _locked_until.tzinfo is None:
            _locked_until = _locked_until.replace(tzinfo=timezone.utc)
        if _locked_until is not None and datetime.now(timezone.utc) < _locked_until:
            raise_error(
                403,
                "ACCOUNT_LOCKED",
                "Account is temporarily locked due to too many failed login attempts. Try again later.",
            )

        if not member.check_password(password):
            member.failed_login_count = (member.failed_login_count or 0) + 1
            if member.failed_login_count >= 5:
                member.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                _log.warning(
                    "Account locked due to too many failed login attempts",
                    extra={
                        "member_id": member.id,
                        "failed_login_count": member.failed_login_count,
                        "locked_until": member.locked_until.isoformat(),
                    },
                )
            else:
                _log.warning(
                    "Failed login attempt",
                    extra={
                        "member_id": member.id,
                        "failed_login_count": member.failed_login_count,
                    },
                )
            db.session.add(member)
            raise_error(401, "UNAUTHORIZED", "Invalid credentials")

        member.failed_login_count = 0
        member.locked_until = None
        return member

    @staticmethod
    def authenticate_user(email: str, password: str) -> User:
        """Authenticate against the global User table.

        Raises 401 for invalid credentials, 403 for disabled accounts (future).
        Does NOT handle tenant-scoped lockout — that remains on Member for now.
        """
        if not email or not password:
            raise_error(401, "UNAUTHORIZED", "Invalid credentials")

        user = db.session.scalar(select(User).where(User.email == email))

        if user is None:
            raise_error(401, "UNAUTHORIZED", "Invalid credentials")

        if not user.check_password(password):
            raise_error(401, "UNAUTHORIZED", "Invalid credentials")

        return user

    @staticmethod
    def resolve_member(user_id: int) -> Member | None:
        """Find the Member record for *user_id* in the current tenant schema.

        Returns None if the user has no Member profile in the current tenant.
        In single-tenant mode (no tenant set), falls back to user_id FK match.
        """
        tenant = current_tenant()
        if tenant is not None:
            return db.session.scalar(
                select(Member).where(
                    Member.user_id == user_id,
                    Member.archived_at.is_(None),
                )
            )
        return db.session.scalar(
            select(Member).where(
                Member.user_id == user_id,
                Member.archived_at.is_(None),
            )
        )

    @staticmethod
    def find_user_tenants(user_id: int) -> list[dict]:
        """Return all tenants the user belongs to.

        Queries UserTenant (public schema) for multi-tenant; falls back to
        scanning tenant schemas for a Member with matching user_id when
        UserTenant records are missing.

        Returns list of {tenant_id, tenant_slug, tenant_name, member_id}.
        """
        from vollbuild.core.models.tenant import Tenant
        from vollbuild.core.tenant.context import set_search_path, reset_search_path

        records = list(
            db.session.scalars(
                select(UserTenant).where(UserTenant.user_id == user_id)
            ).all()
        )
        if records:
            result = []
            for ut in records:
                tenant = db.session.get(Tenant, ut.tenant_id)
                if tenant is None:
                    continue
                set_search_path(tenant.id)
                member_id = db.session.scalar(
                    select(Member.id).where(Member.user_id == user_id)
                )
                reset_search_path()
                result.append(
                    {
                        "tenant_id": ut.tenant_id,
                        "tenant_slug": tenant.slug,
                        "tenant_name": tenant.name,
                        "member_id": member_id,
                    }
                )
            return result

        # Fallback: UserTenant not populated — scan all active tenants
        tenants = list(
            db.session.scalars(select(Tenant).where(Tenant.deleted_at.is_(None))).all()
        )
        found = []
        for tenant in tenants:
            set_search_path(tenant.id)
            member = db.session.scalar(
                select(Member).where(
                    Member.user_id == user_id,
                    Member.archived_at.is_(None),
                )
            )
            reset_search_path()
            if member is not None:
                found.append(
                    {
                        "tenant_id": tenant.id,
                        "tenant_slug": tenant.slug,
                        "tenant_name": tenant.name,
                        "member_id": member.id,
                    }
                )
        if found:
            return found

        # Final fallback: single-tenant mode (SQLite tests, or no tenant
        # schemas created yet). Query Member in the default schema.
        member = db.session.scalar(
            select(Member).where(
                Member.user_id == user_id, Member.archived_at.is_(None)
            )
        )
        if member:
            return [
                {
                    "tenant_id": None,
                    "tenant_slug": None,
                    "tenant_name": None,
                    "member_id": member.id,
                }
            ]
        return []

    @staticmethod
    def record_login(
        member: Member,
        ip: str,
        ua: str,
        fingerprint: str | None = None,
        browser_family: str = "",
        platform: str = "",
    ) -> tuple[bool, int | None]:
        """Record a successful login.

        Creates or reuses a Device row (identified by stable fingerprint)
        and a Session row. If an active session for the same device exists,
        it is reused: jti is rotated and last_active_at is updated.

        Returns (new_device, session_id).
        """
        ua_truncated = ua[:512] if ua else ""
        fp = fingerprint or hashlib.sha256(b"unknown").hexdigest()[:32]

        # Find or create Device by (member_id, fingerprint)
        device = db.session.scalar(
            select(Device)
            .where(Device.member_id == member.id)
            .where(Device.fingerprint == fp)
            .limit(1)
        )
        new_device = device is None

        if device is None:
            # Check if any prior device existed for this member at all
            any_prior = db.session.scalar(
                select(Device.id).where(Device.member_id == member.id).limit(1)
            )
            if any_prior is None:
                create_reason = "first_login"
            else:
                create_reason = "new_device"

            device = Device(
                member_id=member.id,
                fingerprint=fp,
                browser_family=browser_family or None,
                platform=platform or None,
                user_agent=ua_truncated or None,
            )
            db.session.add(device)
            db.session.flush()
        else:
            # Device exists — update UA and last_seen
            device.user_agent = ua_truncated or device.user_agent
            device.last_seen_at = datetime.now(timezone.utc)
            # Determine create_reason if we need a new session
            prior_ip_match = db.session.scalar(
                select(Session.id)
                .join(Device, Session.device_id == Device.id)
                .where(Device.member_id == member.id)
                .where(Device.fingerprint == fp)
                .where(Session.ip_address == ip)
                .limit(1)
            )
            if prior_ip_match is None:
                create_reason = "new_ip"
            elif (
                ua_truncated and device.user_agent and ua_truncated != device.user_agent
            ):
                create_reason = "new_ua"
            else:
                create_reason = "session_expired"

        # Look for an existing active session for this device to reuse
        existing_session = db.session.scalar(
            select(Session)
            .where(Session.device_id == device.id)
            .where(Session.revoked_at.is_(None))
            .order_by(Session.last_active_at.desc())
            .limit(1)
        )
        if existing_session is not None:
            existing_session.jti = secrets.token_hex(16)
            existing_session.last_active_at = datetime.now(timezone.utc)
            existing_session.ip_address = ip[:45] if ip else None
            db.session.add(
                AuditEntry(
                    actor_id=member.id,
                    actor_name=member.name,
                    actor_avatar_color=member.avatar_color,
                    action="login",
                    target_type="Member",
                    target_id=member.id,
                    target_label=member.name,
                    color=member.avatar_color,
                )
            )
            return new_device, existing_session.id

        # Create new Session
        session = Session(
            device_id=device.id,
            jti=secrets.token_hex(16),
            ip_address=ip[:45] if ip else None,
            create_reason=create_reason,
        )
        db.session.add(session)
        db.session.flush()

        db.session.add(
            AuditEntry(
                actor_id=member.id,
                actor_name=member.name,
                actor_avatar_color=member.avatar_color,
                action="login",
                target_type="Member",
                target_id=member.id,
                target_label=member.name,
                color=member.avatar_color,
            )
        )
        return new_device, session.id

    @staticmethod
    def check_locked(identity: str) -> None:
        """Raise 403 if the account is locked."""
        if isinstance(identity, str) and identity.startswith("user:"):
            from vollbuild.core.models.user import User

            user = db.session.get(User, int(identity[5:]))
            if user is None:
                return
            return
        member = db.session.get(Member, int(identity))
        if member is not None:
            _locked_until = member.locked_until
            if _locked_until is not None and _locked_until.tzinfo is None:
                _locked_until = _locked_until.replace(tzinfo=timezone.utc)
            if _locked_until is not None and datetime.now(timezone.utc) < _locked_until:
                raise_error(
                    403,
                    "ACCOUNT_LOCKED",
                    "Account is temporarily locked. Cannot refresh token.",
                )

    @staticmethod
    def block_token(jti: str, token_type: str) -> None:
        """Add a JWT to the blocklist."""
        db.session.add(TokenBlocklist(jti=jti, type=token_type))

    @staticmethod
    def create_password_reset(email: str) -> tuple[str, Member] | None:
        """Create a password reset token for a member. Returns (token, member) or None."""
        if not email:
            return None

        member = db.session.scalar(
            select(Member)
            .join(User, Member.user_id == User.id)
            .where(User.email == email)
            .where(Member.archived_at.is_(None))
        )
        if member is None:
            return None

        existing = db.session.scalars(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == member.user_id)
            .where(PasswordResetToken.used.is_(False))
        ).all()
        for t in existing:
            t.used = True

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        db.session.add(
            PasswordResetToken(
                user_id=member.user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )

        return raw_token, member

    @staticmethod
    def reset_password(raw_token: str, new_password: str) -> Member:
        """Validate reset token and set new password. Returns member."""
        if not raw_token or not new_password:
            raise_error(400, "VALIDATION_ERROR", "token and password are required")

        _enforce_password_strength(new_password)

        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        reset_token = db.session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )

        if reset_token is None or not reset_token.is_valid:
            raise_error(400, "INVALID_TOKEN", "Reset token is invalid or has expired")

        member = db.session.scalar(
            select(Member).where(Member.user_id == reset_token.user_id)
        )
        assert member is not None, f"Member for user {reset_token.user_id} not found"
        member.set_password(new_password)
        member.must_change_password = False
        reset_token.used = True

        db.session.add(
            AuditEntry(
                actor_id=member.id,
                actor_name=member.name,
                actor_avatar_color=member.avatar_color,
                action="reset_password",
                target_type="Member",
                target_id=member.id,
                target_label=member.name,
            )
        )
        return member


class AccountService:
    """Account management business logic."""

    @staticmethod
    def update_account(member: Member, updates: dict) -> tuple[Member, str | None]:
        """Update allowed fields on a member account. Returns (member, new_password)."""
        audit_changes = []

        if "name" in updates:
            full_name = updates["name"].strip() if updates["name"] else ""
            if not full_name:
                raise_error(400, "VALIDATION_ERROR", "Name cannot be empty")
            name_parts = full_name.split(" ", 1)
            member.first_name = name_parts[0]
            member.last_name = name_parts[1] if len(name_parts) > 1 else ""
            audit_changes.append("name")

        if "email" in updates:
            new_email = updates["email"].strip().lower()
            if not _EMAIL_RE.match(new_email):
                raise_error(400, "VALIDATION_ERROR", "Invalid email address")
            conflict = db.session.scalar(
                select(Member.id)
                .join(User, Member.user_id == User.id)
                .where(User.email == new_email)
                .where(Member.id != member.id)
            )
            if conflict is not None:
                raise_error(409, "CONFLICT", "Email already in use")
            member.email = new_email
            member.private_email_verified = False
            _log.info("email_changed member_id=%s — verification reset", member.id)
            audit_changes.append("email")

        if "first_name" in updates:
            first_name = updates["first_name"].strip()
            if not first_name:
                raise_error(400, "VALIDATION_ERROR", "First name cannot be empty")
            member.first_name = first_name
            audit_changes.append("name")

        if "last_name" in updates:
            last_name = updates["last_name"].strip()
            if not last_name:
                raise_error(400, "VALIDATION_ERROR", "Last name cannot be empty")
            member.last_name = last_name
            audit_changes.append("name")

        if "avatar" in updates:
            av = updates["avatar"]
            if av is not None and len(str(av)) > 2 * 1024 * 1024:
                raise_error(400, "VALIDATION_ERROR", "Avatar exceeds maximum size")
            member.avatar = _sanitize_svg_avatar(av)
            audit_changes.append("avatar")

        if "avatar_color" in updates:
            color = updates["avatar_color"]
            if color and len(color) == 7 and color.startswith("#"):
                member.avatar_color = color
            audit_changes.append("avatar_color")

        if "profile_note" in updates:
            note = updates["profile_note"]
            if note is not None and len(str(note)) > 5000:
                raise_error(
                    400, "VALIDATION_ERROR", "Profile note exceeds 5000 characters"
                )
            member.profile_note = note
            audit_changes.append("profile_note")

        new_password: str | None = None
        if "password" in updates:
            new_password = updates["password"]
            if not new_password or len(new_password) < 8:
                raise_error(
                    400, "VALIDATION_ERROR", "Password must be at least 8 characters"
                )
            member.set_password(new_password)
            member.must_change_password = False
            audit_changes.append("password")

        if audit_changes:
            db.session.add(
                AuditEntry(
                    actor_id=member.id,
                    actor_name=member.name,
                    actor_avatar_color=member.avatar_color,
                    action="update_account",
                    target_type="Member",
                    target_id=member.id,
                    target_label=member.name,
                )
            )

        return member, new_password

    @staticmethod
    def change_password(
        member: Member, current_password: str, new_password: str
    ) -> None:
        """Validate current password and set new password."""
        if not current_password or not new_password:
            raise_error(
                400,
                "VALIDATION_ERROR",
                "currentPassword and newPassword are required",
            )

        _enforce_password_strength(new_password)

        if not member.check_password(current_password):
            raise_error(401, "UNAUTHORIZED", "Current password is incorrect")

        member.set_password(new_password)
        member.must_change_password = False

        db.session.add(
            AuditEntry(
                actor_id=member.id,
                actor_name=member.name,
                actor_avatar_color=member.avatar_color,
                action="change_password",
                target_type="Member",
                target_id=member.id,
                target_label=member.name,
            )
        )

    @staticmethod
    def get_invoices(member_id: int) -> list[Invoice]:
        """Return invoices for a member."""
        return db.session.scalars(  # type: ignore[return-value]
            select(Invoice).where(Invoice.member_id == member_id)
        ).all()

    @staticmethod
    def get_groups(member: Member) -> list:
        """Return groups for a member."""
        return list(member.groups)

    @staticmethod
    def update_mail_settings(member: Member, updates: dict) -> list[str]:
        """Update mail-related settings. Returns list of changed field names."""
        from vollbuild.core.models.managed_mail import ManagedMailAddress

        addr = db.session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "member",
                ManagedMailAddress.owner_id == member.id,
            )
        )

        if "forwarding_enabled" in updates:
            if (
                updates["forwarding_enabled"] is True
                and not member.private_email_verified
            ):
                _log.warning(
                    "update_account_mail_settings: member %s attempted forwarding_enabled=true without verified private email",
                    member.id,
                )
                raise_error(
                    422,
                    "VERIFICATION_REQUIRED",
                    "Private email must be verified before enabling forwarding",
                )
            if not isinstance(updates["forwarding_enabled"], bool):
                raise_error(
                    400, "VALIDATION_ERROR", "forwarding_enabled must be a boolean"
                )

        changed = []
        if "forwarding_enabled" in updates and addr is not None:
            addr.forwarding_enabled = updates["forwarding_enabled"]
            changed.append("forwarding_enabled")

        if changed:
            db.session.add(
                AuditEntry(
                    actor_id=member.id,
                    actor_name=member.name,
                    actor_avatar_color=member.avatar_color,
                    action="update_mail_settings",
                    target_type="Member",
                    target_id=member.id,
                    target_label=member.name,
                )
            )

        return changed

    @staticmethod
    def create_email_verification_token(member: Member) -> str:
        """Create an email verification token. Returns the raw token."""
        existing = db.session.scalars(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == member.user_id)
            .where(EmailVerificationToken.used.is_(False))
        ).all()
        for t in existing:
            t.used = True

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        db.session.add(
            EmailVerificationToken(
                user_id=member.user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        return raw_token

    @staticmethod
    def verify_email(raw_token: str) -> Member:
        """Verify an email verification token. Returns the member."""
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        evt = db.session.scalar(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == token_hash
            )
        )

        if evt is None or not evt.is_valid:
            raise_error(
                400, "INVALID_TOKEN", "Verification link is invalid or has expired"
            )

        member = db.session.scalar(select(Member).where(Member.user_id == evt.user_id))
        assert member is not None, f"Member for user {evt.user_id} not found"
        member.private_email_verified = True
        evt.used = True
        return member
