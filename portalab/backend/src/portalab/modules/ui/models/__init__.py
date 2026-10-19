"""Schema ``ui`` (specs/022-personalization-themes-a11y/data-model.md): registered themes. Themes are public
configuration (no personal data); they are disabled, never deleted, while preferences may reference them.
Issue 159: the site's identity (its name, slogan, logo, icon and currency) — one row, public too."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Integer, LargeBinary, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal


class UiBase(DeclarativeBase):
    metadata = schema_metadata("ui")


class Theme(UiBase):
    __tablename__ = "themes"
    __table_args__ = (UniqueConstraint("key", name="uq_themes_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False, info=not_personal("theme label"))
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    floor_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class SiteIdentity(UiBase):
    """Issue 159: what the members read instead of « Portalab » and « Coins » (``None``: Portalab's own)."""

    __tablename__ = "site_identity"
    __table_args__ = (CheckConstraint("id = 1", name="ck_site_identity_single"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    name: Mapped[str | None] = mapped_column(String(40), info=not_personal("the site's name"))
    short_name: Mapped[str | None] = mapped_column(String(12), info=not_personal("the site's short name"))
    # per language: {"fr": "Vos services…"}; currency: {"fr": {"one": "Xénocoin", "other": "Xénocoins"}}
    tagline: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    currency: Mapped[dict[str, dict[str, str]]] = mapped_column(JSONB, nullable=False, default=dict)
    currency_short: Mapped[str | None] = mapped_column(String(8))
    currency_icon: Mapped[str | None] = mapped_column(String(32))
    logo: Mapped[bytes | None] = mapped_column(LargeBinary)
    logo_type: Mapped[str | None] = mapped_column(String(32))
    icon: Mapped[bytes | None] = mapped_column(LargeBinary)
    icon_type: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
