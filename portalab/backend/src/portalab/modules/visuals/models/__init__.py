"""Schema ``visuals`` (specs/028-visual-packs/data-model.md): the registry of visual packs — packs, their
versions (each one's analysis, measures and decision), their elements, the looks the live ones claim, the
booster scenes bound, and the registry's epoch (what every process compares to know it must reload).

Pack files are not here: each version's files live on disk under their fingerprint, never changed. Packs hold
no personal data (the ids of who decided are kept in the decision, as in the audit log)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id

PACK_STATES = ("enabled", "disabled", "archived", "removed")
STEPS = ("imported", "analysed", "tested", "reviewed", "published", "refused", "superseded", "purged")


class VisualsBase(DeclarativeBase):
    metadata = schema_metadata("visuals")


class Pack(VisualsBase):
    __tablename__ = "packs"
    __table_args__ = (Index("uq_packs_socle", "socle", unique=True, postgresql_where=text("socle")),)

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    socle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="disabled")
    current_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    remote: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    names: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class PackVersion(VisualsBase):
    __tablename__ = "pack_versions"
    __table_args__ = (UniqueConstraint("pack_id", "version", name="uq_pack_versions_number"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    pack_id: Mapped[str] = mapped_column(ForeignKey("visuals.packs.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    folder: Mapped[str] = mapped_column(String(200), nullable=False)
    step: Mapped[str] = mapped_column(String(16), nullable=False, default="imported")
    outcomes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    measures: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    decision: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ever_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detected_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)


class Element(VisualsBase):
    __tablename__ = "elements"
    __table_args__ = (Index("ix_elements_type_look", "type", "look"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("visuals.pack_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    folder: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    look: Mapped[str | None] = mapped_column(String(48), nullable=True)
    product_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class LookClaim(VisualsBase):
    """A look a live pack holds — ``(type, look)`` is unique: two packs can never publish the same one."""

    __tablename__ = "look_claims"

    type: Mapped[str] = mapped_column(String(32), primary_key=True)
    look: Mapped[str] = mapped_column(String(48), primary_key=True)
    pack_id: Mapped[str] = mapped_column(ForeignKey("visuals.packs.id"), nullable=False, index=True)
    element_id: Mapped[UUID] = mapped_column(nullable=False)
    replaced_from: Mapped[str | None] = mapped_column(String(48), nullable=True)


class SceneBinding(VisualsBase):
    __tablename__ = "scene_bindings"

    booster_key: Mapped[str] = mapped_column(String(64), primary_key=True)  # ``*``: every booster
    element_id: Mapped[UUID] = mapped_column(nullable=False)
    bound_by: Mapped[UUID | None] = mapped_column(nullable=True)
    bound_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class RegistryEpoch(VisualsBase):
    __tablename__ = "registry_epoch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
