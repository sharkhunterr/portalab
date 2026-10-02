"""Schema ``i18n`` (specs/026-i18n/data-model.md): known languages, admin catalog overrides, catalog
versions, the multilingual content version registry and missing-key statistics. No personal data;
enablement lives in configuration (CD-011)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal


class I18nBase(DeclarativeBase):
    metadata = schema_metadata("i18n")


class Language(I18nBase):
    __tablename__ = "languages"
    __table_args__ = (CheckConstraint("direction IN ('ltr', 'rtl')", name="direction"),)

    code: Mapped[str] = mapped_column(String(35), primary_key=True)
    name_native: Mapped[str] = mapped_column(String(80), nullable=False, info=not_personal("language name"))
    name_en: Mapped[str] = mapped_column(String(80), nullable=False, info=not_personal("language name"))
    direction: Mapped[str] = mapped_column(String(3), nullable=False)
    fallback_code: Mapped[str | None] = mapped_column(ForeignKey("i18n.languages.code"))
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class CatalogEntry(I18nBase):
    __tablename__ = "catalog_entries"
    __table_args__ = (
        UniqueConstraint("namespace", "key", "language", name="uq_catalog_entries"),
        CheckConstraint("state IN ('draft', 'published', 'deprecated')", name="state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    language: Mapped[str] = mapped_column(ForeignKey("i18n.languages.code"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, info=not_personal("interface text"))
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_by: Mapped[UUID | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class CatalogVersion(I18nBase):
    __tablename__ = "catalog_versions"

    namespace: Mapped[str] = mapped_column(String(64), primary_key=True)
    language: Mapped[str] = mapped_column(String(35), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class LocalizedContentVersion(I18nBase):
    __tablename__ = "localized_content_versions"
    __table_args__ = (
        UniqueConstraint(
            "content_kind", "content_id", "language", "version", name="uq_localized_content_versions"
        ),
        CheckConstraint("state IN ('source', 'translated', 'untranslated', 'machine_draft')", name="state"),
        Index("ix_localized_content_lookup", "content_kind", "content_id", "language"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    content_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    content_id: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str] = mapped_column(ForeignKey("i18n.languages.code"), nullable=False)
    source_language: Mapped[str] = mapped_column(ForeignKey("i18n.languages.code"), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    translation_of_version: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class MissingKeyStat(I18nBase):
    __tablename__ = "missing_key_stats"

    namespace: Mapped[str] = mapped_column(String(64), primary_key=True)
    language: Mapped[str] = mapped_column(String(35), primary_key=True)
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
