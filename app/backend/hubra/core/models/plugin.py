"""Plugins: what this platform has installed, the archives, and where they come from.

All public-schema tables.  A plugin is installed for the whole platform;
each club then switches its modules on or off (``TenantFeature``).

``InstalledPlugin`` is the desired state every backend, worker and beat
process follows: on start (and when ``plugin_state.generation`` changes)
each one unpacks the archive of every installed plugin from
``PluginArchive`` into its own plugin folder, checks the signature again
and loads it.  So pods need no shared volume and no network to start.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PluginRepository(db.Model):
    """A signed plugin index.  ``key_id``/``public_key`` is its index key;
    ``plugin_keys`` (JSON, the index's ``plugin_keys``) the keys its plugins
    are signed with.  Both are pinned when it is added.  An empty
    ``plugin_keys`` is the old format: the index key signs the plugins too.
    The official repository takes its keys from the image instead."""

    __tablename__ = "plugin_repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    key_id: Mapped[str] = mapped_column(String(16), nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    added_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # ``generated`` of the newest index seen: an older one is refused, so a
    # mirror can't serve a stale (still validly signed) index with old,
    # vulnerable versions.
    index_generated: Mapped[str] = mapped_column(
        String(40), default="", server_default="", nullable=False
    )
    plugin_keys: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )


class TrustedKey(db.Model):
    """A signing key a platform manager chose to trust (community).

    ``purpose`` is what the key may sign; only "plugins" can be added by
    hand, since an index key belongs to its repository."""

    __tablename__ = "plugin_trusted_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(
        String(16), default="plugins", server_default="plugins", nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    key_id: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    added_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class InstalledPlugin(db.Model):
    """One installed plugin.  ``archive_sha256`` names the archive in use;
    ``previous_sha256`` the one an update replaced (to roll back to)."""

    __tablename__ = "installed_plugins"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    # bundled: shipped in the image, nothing to unpack.  archive: from a
    # repository or an upload, unpacked from PluginArchive.
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    origin: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    repository_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("plugin_repositories.id", ondelete="SET NULL"),
        nullable=True,
    )
    trust: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    signer: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    key_id: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    archive_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    held_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    installed_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    # A problem one of the processes hit while loading it (shown to managers).
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)

    def __repr__(self) -> str:
        return f"<InstalledPlugin {self.id} {self.version}>"


class PluginArchive(db.Model):
    """A plugin's zip, as downloaded or uploaded (signature checked)."""

    __tablename__ = "plugin_archives"
    __table_args__ = (UniqueConstraint("sha256", name="uq_plugin_archive_sha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Deferred: lists and checks only need the version and hash; the zip
    # (up to a few MB each, every kept version) loads when read.
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class PluginState(db.Model):
    """Small platform-wide plugin settings: ``generation`` (bumped on every
    install, update or removal so all processes reload), the update mode,
    and what update notices were already shown."""

    __tablename__ = "plugin_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
