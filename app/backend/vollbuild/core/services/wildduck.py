"""WildDuck REST API client.

Wraps all HTTP calls to the WildDuck mail server API. All methods raise
WildDuckError on API-level failures. Callers should catch it and log/skip
gracefully so that mail-server unavailability never blocks Flask routes.

Uses urllib3 for connection pooling (keepalive) and automatic retries with
exponential backoff on transient errors (connection failures, 5xx responses).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
import urllib.parse
from typing import Any

import urllib3
from flask import current_app

logger = logging.getLogger(__name__)

# Retry configuration: 3 attempts, exponential backoff (0.5s, 1s, 2s).
# Retry on connection errors and 5xx server errors. Never retry 4xx (client errors).
_RETRY_CONFIG = urllib3.util.retry.Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[502, 503, 504],
    allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    raise_on_status=False,
)


class WildDuckError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(f"WildDuck {status}: {message}")


class WildDuckClient:
    """HTTP wrapper around the WildDuck REST API with retry and connection pooling."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._http = urllib3.PoolManager(
            maxsize=10,
            retries=_RETRY_CONFIG,
            timeout=urllib3.Timeout(connect=5, read=10),
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _req(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        if params:
            qs = "&".join(
                f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}"
                for k, v in params.items()
            )
            path = f"{path}?{qs}" if "?" not in path else f"{path}&{qs}"
        url = f"{self._base}{path}"
        logger.debug("WildDuck %s %s", method, url)
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "X-Access-Token": self._token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            resp = self._http.request(method, url, body=data, headers=headers)
        except urllib3.exceptions.MaxRetryError as exc:
            raise WildDuckError(0, f"Connection failed after retries: {exc}") from exc
        except urllib3.exceptions.ProtocolError as exc:
            raise WildDuckError(0, f"Protocol error: {exc}") from exc

        body_bytes = resp.data
        if resp.status >= 400:
            try:
                detail = json.loads(body_bytes.decode()).get(
                    "error", body_bytes.decode()
                )
            except Exception:
                detail = body_bytes.decode(errors="replace")
            raise WildDuckError(resp.status, detail)

        if resp.status == 204 or not body_bytes:
            return {}
        return json.loads(body_bytes.decode())

    # ── Pagination helper ─────────────────────────────────────────────────────

    def _paginated_get(self, path: str, limit: int = 250) -> dict:
        """Fetch all pages from a paginated WildDuck GET endpoint.

        WildDuck paginates with ``page`` and ``limit`` (max 250). The
        response shape is ``{"results": [...], "total": N}``.  Continues
        fetching while ``len(all_results) < total``.
        """
        all_results: list[dict] = []
        page = 1
        while True:
            sep = "&" if "?" in path else "?"
            resp = self._req("GET", f"{path}{sep}limit={limit}&page={page}")
            batch = resp.get("results", [])
            all_results.extend(batch)
            total = resp.get("total", 0)
            if not batch or len(all_results) >= total:
                break
            page += 1
        return {"results": all_results, "total": total or len(all_results)}

    # ── Users / Mailboxes ─────────────────────────────────────────────────────

    def list_users(self, query: str = "", limit: int = 250, page: int = 1) -> dict:
        qs = f"?limit={limit}&page={page}" + (
            f"&query={urllib.parse.quote(query)}" if query else ""
        )
        return self._req("GET", f"/users{qs}")

    def create_user(
        self,
        username: str,
        name: str,
        password: str,
        quota_mb: int = 1024,
        hashed: bool = False,
        retention_ms: int | None = None,
        targets: list[str] | None = None,
    ) -> dict:
        """Create a WildDuck user (mailbox). Returns ``{"id": "...", ...}``.

        Pass ``hashed=True`` when *password* is an argon2id hash so WildDuck
        stores it directly (rehashes to pbkdf2 on first successful auth).
        ``targets`` is initialized to ``[]`` (or the provided list) to prevent
        a null-read bug in WildDuck's MongoDB layer on subsequent updates.
        When ``retention_ms`` is set, messages older than this are auto-purged.
        """
        body: dict[str, Any] = {
            "username": username,
            "name": name,
            "password": password,
            "quota": quota_mb * 1024 * 1024,
            "targets": targets or [],
        }
        if hashed:
            body["hashedPassword"] = True
        if retention_ms is not None:
            body["retention"] = retention_ms
        return self._req("POST", "/users", body)

    def get_user(self, user_id: str) -> dict:
        return self._req("GET", f"/users/{user_id}")

    def update_user(self, user_id: str, **fields: Any) -> dict:
        return self._req("PUT", f"/users/{user_id}", fields)

    def update_user_password(
        self, user_id: str, password: str, hashed: bool = False
    ) -> dict:
        body: dict[str, Any] = {"password": password}
        if hashed:
            body["hashedPassword"] = True
        return self._req("PUT", f"/users/{user_id}", body)

    def update_user_attributes(self, user_id: str, **fields: Any) -> dict:
        """Update arbitrary fields on a WildDuck user.

        Typical fields: ``name``, ``quota`` (bytes), ``retention`` (ms),
        ``targets`` (list of str), ``fromWhitelist``.
        """
        return self._req("PUT", f"/users/{user_id}", fields)

    def get_user_quota(self, user_id: str) -> dict:
        """Return quota usage for a user: ``{"used": int, "allowed": int}``.

        Returns an empty dict if quota info is not available.
        """
        resp = self.safe_get_user(user_id)
        if resp is None:
            return {}
        quota = resp.get("quota", {})
        if isinstance(quota, dict):
            return {"used": quota.get("used", 0), "allowed": quota.get("allowed", 0)}
        return {}

    def delete_user(self, user_id: str) -> dict:
        return self._req("DELETE", f"/users/{user_id}")

    def safe_get_user(self, user_id: str) -> dict | None:
        """Return user dict, or None on 404."""
        try:
            return self.get_user(user_id)
        except WildDuckError as exc:
            if exc.status == 404:
                return None
            raise

    def safe_delete_user(self, user_id: str) -> bool:
        """Delete a WildDuck user. Returns True if deleted, False if already gone (404)."""
        try:
            self.delete_user(user_id)
            return True
        except WildDuckError as exc:
            if exc.status == 404:
                return False
            raise

    # ── Addresses / Aliases ───────────────────────────────────────────────────

    def list_addresses(self) -> dict:
        """List all forwarding addresses, auto-paginating."""
        return self._paginated_get("/addresses")

    def get_address(self, address_id: str) -> dict:
        return self._req("GET", f"/addresses/{address_id}")

    def safe_get_address(self, address_id: str) -> dict | None:
        """Return address dict, or None on 404."""
        try:
            return self.get_address(address_id)
        except WildDuckError as exc:
            if exc.status == 404:
                return None
            raise

    def add_address_to_user(
        self,
        user_id: str,
        address: str,
        main: bool = False,
        allow_wildcard: bool = False,
    ) -> dict:
        return self._req(
            "POST",
            f"/users/{user_id}/addresses",
            {
                "address": address,
                "main": main,
                "allowWildcard": allow_wildcard,
            },
        )

    def list_user_addresses(self, user_id: str) -> dict:
        return self._req("GET", f"/users/{user_id}/addresses")

    def create_forwarding_alias(
        self,
        address: str,
        targets: list[str],
        name: str = "",
        allow_wildcard: bool = False,
    ) -> dict:
        """Create a forwarding alias that delivers to *targets*.

        If the address already exists in WildDuck, update it instead of
        failing with a 400 error.
        """
        existing = self.find_forwarding_alias_by_address(address)
        if existing is not None:
            alias_id: str = str(existing.get("id", ""))
            logger.info(
                "create_forwarding_alias: address %s already exists (id=%s), updating",
                address,
                alias_id,
            )
            return self.update_forwarding_alias(alias_id, targets)
        return self._req(
            "POST",
            "/addresses/forwarded",
            {
                "address": address,
                "name": name or address,
                "targets": targets,
                "allowWildcard": allow_wildcard,
            },
        )

    def find_forwarding_alias_by_address(self, address: str) -> dict | None:
        """Find a forwarded alias by its address. Returns None if not found."""
        page = 0
        while True:
            resp = self._req(
                "GET",
                "/addresses/forwarded",
                params={"page": str(page), "page_size": "100"},
            )
            results = resp.get("results", [])
            if not results:
                break
            for entry in results:
                if entry.get("address", "").lower() == address.lower():
                    return entry
            if len(results) < 100:
                break
            page += 1
        return None

    def update_forwarding_alias(self, alias_id: str, targets: list[str]) -> dict:
        return self._req(
            "PUT", f"/addresses/forwarded/{alias_id}", {"targets": targets}
        )

    def delete_forwarding_alias(self, alias_id: str) -> dict:
        return self._req("DELETE", f"/addresses/forwarded/{alias_id}")

    def safe_delete_forwarding_alias(self, alias_id: str) -> bool:
        """Delete a forwarding alias. Returns True if deleted, False if already gone (404)."""
        try:
            self.delete_forwarding_alias(alias_id)
            return True
        except WildDuckError as exc:
            if exc.status == 404:
                return False
            raise

    def delete_address(self, address_id: str) -> dict:
        return self._req("DELETE", f"/addresses/{address_id}")

    def safe_delete_address(self, address_id: str) -> bool:
        """Delete an address. Returns True if deleted, False if already gone (404)."""
        try:
            self.delete_address(address_id)
            return True
        except WildDuckError as exc:
            if exc.status == 404:
                return False
            raise

    # ── Messages (for mail log) ───────────────────────────────────────────────

    def list_user_messages(
        self, user_id: str, mailbox: str = "INBOX", limit: int = 25, page: int = 1
    ) -> dict:
        return self._req(
            "GET",
            f"/users/{user_id}/mailboxes/{mailbox}/messages?limit={limit}&page={page}",
        )

    def delete_user_message(self, user_id: str, mailbox: str, message_id: str) -> dict:
        return self._req(
            "DELETE", f"/users/{user_id}/mailboxes/{mailbox}/messages/{message_id}"
        )

    # ── Webhooks (cleanup only) ────────────────────────────────────────────────

    def list_webhooks(self) -> dict:
        return self._req("GET", "/webhooks")

    def delete_webhook(self, webhook_id: str) -> dict:
        return self._req("DELETE", f"/webhooks/{webhook_id}")

    # ── IMAP mailboxes (folders) ───────────────────────────────────────────────

    def list_mailboxes(self, user_id: str, counters: bool = True) -> dict:
        """Return per-folder mailbox metadata for a WildDuck user.

        When *counters* is True (default), each entry includes ``messages``
        (total) and ``unseen`` (unread) counts.
        """
        return self._req(
            "GET",
            f"/users/{user_id}/mailboxes",
            params={"counters": "true" if counters else "false"},
        )

    # ── Filters (member forwarding) ────────────────────────────────────────────

    def create_forward_filter(self, user_id: str, forward_to: str) -> dict:
        """Create a filter that forwards all inbound mail to *forward_to*.

        An empty ``query`` object matches every message.  The ``targets``
        array in ``action`` is how WildDuck encodes forwarding.
        """
        return self._req(
            "POST",
            f"/users/{user_id}/filters",
            {
                "name": "Auto-forward",
                "query": {},
                "action": {
                    "targets": [forward_to],
                },
            },
        )

    def delete_forward_filter(self, user_id: str, filter_id: str) -> dict:
        """Remove a filter by its ID."""
        return self._req("DELETE", f"/users/{user_id}/filters/{filter_id}")

    # ── Send-as ACL stubs ─────────────────────────────────────────────────────

    def add_allowed_from(self, user_id: str, group_address: str) -> None:
        """Grant send-as permission for a group address to a WildDuck user.

        WildDuck does not expose a dedicated send-as ACL endpoint in its standard
        REST API. This stub logs a WARNING and takes no action — it can be upgraded
        to a real API call when a confirmed endpoint is available.
        """
        logger.warning(
            "WildDuck send-as ACL not supported natively: skipping grant of %s for user %s",
            group_address,
            user_id,
        )

    def remove_allowed_from(self, user_id: str, group_address: str) -> None:
        """Revoke send-as permission for a group address from a WildDuck user.

        WildDuck does not expose a dedicated send-as ACL endpoint in its standard
        REST API. This stub logs a WARNING and takes no action — it can be upgraded
        to a real API call when a confirmed endpoint is available.
        """
        logger.warning(
            "WildDuck send-as ACL not supported natively: skipping revoke of %s for user %s",
            group_address,
            user_id,
        )


# ── Module-level helpers ──────────────────────────────────────────────────────


def get_client() -> WildDuckClient:
    """Return a configured WildDuckClient for the current app context."""
    url = current_app.config.get("WILDDUCK_API_URL", "")
    token = current_app.config.get("WILDDUCK_API_TOKEN", "")
    if not url or not token:
        raise WildDuckError(
            0, "WildDuck not configured (WILDDUCK_API_URL / WILDDUCK_API_TOKEN missing)"
        )
    return WildDuckClient(url, token)


def try_get_client() -> WildDuckClient | None:
    """Return a client, or None (with a debug log) if WildDuck is not configured."""
    try:
        return get_client()
    except WildDuckError:
        logger.debug("WildDuck not configured — mail integration skipped")
        return None


def make_username(name: str) -> str:
    """Convert a display name to a WildDuck-safe ASCII username.

    "Marco Köhler" → "marco.kohler"
    """
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", ".", ascii_str.lower()).strip(".")
    return slug or "member"


def apply_email_schema(name: str, schema: str, domain: str) -> str:
    """Generate a club email address from a display name using the configured schema.

    Ports the frontend applySchema TypeScript function exactly:
    - Umlaut substitution (ä→ae, ö→oe, ü→ue) before stripping non-alpha
    - Schemas: 'firstname.lastname', 'f.lastname', 'firstname', 'flastname', 'f.ll'
    """

    def _norm(s: str) -> str:
        s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        return re.sub(r"[^a-z]", "", s)

    parts = name.strip().split()
    first = _norm(parts[0]) if parts else "member"
    last = _norm("".join(parts[1:])) if len(parts) > 1 else ""

    if schema == "f.lastname":
        local = f"{first[:1]}.{last}" if first and last else (first or last)
    elif schema == "firstname":
        local = first or "member"
    elif schema == "flastname":
        local = f"{first[:1]}{last}" if first and last else (first or last)
    elif schema == "f.ll":
        local = (
            f"{first[:1]}.{last[:2]}"
            if first and last
            else (first or last[:2] or "member")
        )
    else:  # "firstname.lastname" (default)
        local = f"{first}.{last}" if last else first

    return f"{local or 'member'}@{domain}"
