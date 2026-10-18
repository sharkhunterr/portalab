"""Schema ``plugins`` (specs/023 data-model): installed plugins and their state, append-only versions (with
the manifest, the on-disk package and its checksum), the contribution ledger, the install-time review
(consent) record, bounded error statistics, append-only purges and update runs. Users are referenced by id
(FK in the migration only). Plugin data itself lives in schemas ``plugin_<key>``."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

STATES = (
    "installed",
    "needs_configuration",
    "enabled",
    "disabled",
    "update_pending",
    "update_failed",
    "incompatible",
    "quarantined",
    "archived",
    "held_unconfined",  # 030: its code would run in Portalab's process, which the Admin does not allow
    "held_confinement",  # 030: the system cannot confine it and the weaker mode is off
)
RUNTIMES = ("declarative", "in_process", "confined")
ATTEMPTS = (
    "denied_capability", "denied_operation", "denied_host", "private_address", "oversize", "timeout",
    "unresponsive", "memory", "crash", "busy", "storage_quota", "rate", "confinement", "denied_statement",
)  # fmt: skip


class PluginsBase(DeclarativeBase):
    metadata = schema_metadata("plugins")


class Plugin(PluginsBase):
    __tablename__ = "plugins"
    __table_args__ = (
        CheckConstraint("state IN (" + ", ".join(f"'{s}'" for s in STATES) + ")", name="state"),
        CheckConstraint("scope IN ('portal', 'user')", name="scope"),
        CheckConstraint("source IN ('admin_upload', 'local_dir', 'marketplace')", name="source"),
        CheckConstraint("runtime IN (" + ", ".join(f"'{r}'" for r in RUNTIMES) + ")", name="runtime"),
    )

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("a plugin name"))
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    maturity: Mapped[str] = mapped_column(String(12), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    current_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    needs_restart: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    installed_by: Mapped[UUID | None] = mapped_column()
    installed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    enabled_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    quarantine_reason: Mapped[str | None] = mapped_column(
        String(300), info=not_personal("a technical reason")
    )
    last_error_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    state_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    # spec 030
    runtime: Mapped[str] = mapped_column(String(12), nullable=False, default="declarative")
    confinement: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # installed before confinement existed: its in-process code keeps running (plugins.unconfined=existing)
    predates_confinement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PluginVersion(PluginsBase):
    __tablename__ = "versions"
    __table_args__ = (
        CheckConstraint("status IN ('current', 'previous', 'staged', 'failed', 'probation')", name="status"),
        {"info": APPEND_ONLY_INFO},
    )

    plugin_key: Mapped[str] = mapped_column(ForeignKey("plugins.plugins.key"), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    package_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class VersionState(PluginsBase):
    """Mutable status of a version (``versions`` itself is append-only)."""

    __tablename__ = "version_states"

    plugin_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    probation_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Contribution(PluginsBase):
    __tablename__ = "contributions"
    __table_args__ = (
        CheckConstraint("state IN ('active', 'removed', 'conflict')", name="state"),
        Index("ix_contributions_plugin", "plugin_key", "state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    point: Mapped[str] = mapped_column(String(32), nullable=False)
    contribution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(8), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    detail: Mapped[str | None] = mapped_column(String(300), info=not_personal("a technical note"))
    registered_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Review(PluginsBase):
    __tablename__ = "reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column()
    approved_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    permissions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    extension_points: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    events: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    personal_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capabilities: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class ErrorStat(PluginsBase):
    __tablename__ = "error_stats"
    __table_args__ = (
        CheckConstraint("kind IN ('route', 'event', 'action', 'widget', 'job', 'load', 'hook')", name="kind"),
    )

    plugin_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sample: Mapped[str | None] = mapped_column(String(300), info=not_personal("a sanitized error type"))


class Purge(PluginsBase):
    __tablename__ = "purges"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column()
    exported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    export_ref: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    schema_dropped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UpdateRun(PluginsBase):
    __tablename__ = "update_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'migrated', 'pending_restart', 'probation', 'succeeded', 'rolled_back', "
            "'failed')",
            name="status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    from_version: Mapped[str] = mapped_column(String(64), nullable=False)
    to_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, info=not_personal("a sanitized error"))
    probation_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


# --- spec 030: confined plugins ----------------------------------------------------------------------------
class Grant(PluginsBase):
    """A capability the Admin accepted for one version of a plugin (revocable at once)."""

    __tablename__ = "grants"
    __table_args__ = (UniqueConstraint("plugin_key", "version", "capability"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(24), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    granted_by: Mapped[UUID | None] = mapped_column()
    granted_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Attempt(PluginsBase):
    """Something a plugin tried and was refused, or a limit it broke; counted toward quarantine."""

    __tablename__ = "attempts"
    __table_args__ = (
        CheckConstraint("kind IN (" + ", ".join(f"'{k}'" for k in ATTEMPTS) + ")", name="kind"),
        Index("ix_attempts_plugin", "plugin_key", "occurred_at"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class NetworkCall(PluginsBase):
    """Hourly counters of a plugin's outgoing calls, per host."""

    __tablename__ = "network_calls"

    plugin_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    host: Mapped[str] = mapped_column(String(253), primary_key=True, info=not_personal("a host name"))
    hour: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    calls: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    refused: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bytes_in: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bytes_out: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class SecretSetting(PluginsBase):
    """A secret a plugin needs (kept encrypted by Portalab, never sent to the plugin)."""

    __tablename__ = "secret_settings"

    plugin_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(48), primary_key=True, info=not_personal("a setting's name"))
    ciphertext: Mapped[str] = mapped_column(
        Text, nullable=False, info=not_personal("an encrypted credential")
    )
    updated_by: Mapped[UUID | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class SlotSetting(PluginsBase):
    """The Admin's portal-wide order and visibility of a contribution in a slot."""

    __tablename__ = "slot_settings"

    slot: Mapped[str] = mapped_column(String(32), primary_key=True)
    contribution: Mapped[str] = mapped_column(String(160), primary_key=True)
    position: Mapped[int | None] = mapped_column(Integer)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Confirmation(PluginsBase):
    """A single-use confirmation of a member for a committing plugin operation (its exact content)."""

    __tablename__ = "confirmations"

    token_hash: Mapped[bytes] = mapped_column(
        LargeBinary, primary_key=True, info=not_personal("the hash of a single-use confirmation")
    )
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    plugin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(140), nullable=False)
    body_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TZDateTime)
