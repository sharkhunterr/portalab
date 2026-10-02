"""Admin catalog entries (T019; FR-011, FR-034): validated overrides and admin-authored strings — ICU
syntax and placeholder parity with the source language — audited, versioned (``catalog_version`` +
``catalog_versions`` content hash), announced as ``i18n.translation_updated``."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.i18n import LocaleContext
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.i18n.catalog.service import CatalogService, valid_namespace
from portalab.modules.i18n.models import CatalogEntry, CatalogVersion, Language
from portalab.modules.i18n.render.icu import MessageSyntaxError, arguments_of, parse


class InvalidMessage(ValidationFailed):
    default_code = "i18n.invalid_message"


class PlaceholderMismatch(ValidationFailed):
    default_code = "i18n.placeholder_mismatch"


class UnknownLanguage(ValidationFailed):
    default_code = "i18n.language_unknown"


class CatalogAdmin:
    def __init__(
        self,
        database: Database,
        catalogs: CatalogService,
        audit: AuditSink,
        events: EventPublisher,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.catalogs = catalogs
        self.audit = audit
        self.events = events
        self.clock = clock

    async def entries(
        self, namespace: str | None = None, language: str | None = None
    ) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            statement = select(CatalogEntry).order_by(
                CatalogEntry.namespace, CatalogEntry.key, CatalogEntry.language
            )
            if namespace:
                statement = statement.where(CatalogEntry.namespace == namespace)
            if language:
                statement = statement.where(CatalogEntry.language == language)
            return [
                {
                    "namespace": r.namespace,
                    "key": r.key,
                    "language": r.language,
                    "message": r.message,
                    "state": r.state,
                    "catalog_version": r.catalog_version,
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in (await session.execute(statement)).scalars()
            ]

    async def put(
        self,
        actor: Principal,
        *,
        namespace: str,
        key: str,
        language: str,
        message: str,
        state: str = "published",
    ) -> dict[str, Any]:
        if not valid_namespace(namespace):
            raise ValidationFailed("Invalid namespace.", code="i18n.invalid_namespace")
        try:
            names = arguments_of(parse(message))
        except MessageSyntaxError as exc:
            raise InvalidMessage(f"The message is not valid ICU: {exc}") from exc
        source, _ = self.catalogs.lookup(namespace, key, LocaleContext(language="en", fallback_chain=()))
        if source is not None and language != "en" and names != arguments_of(parse(source)):
            raise PlaceholderMismatch(
                "The message must use the same placeholders as the source text.",
                extensions={"expected": sorted(arguments_of(parse(source))), "found": sorted(names)},
            )
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            if await uow.session.get(Language, language) is None:
                raise UnknownLanguage("Unknown language.")
            current = (
                await uow.session.execute(
                    select(CatalogEntry.catalog_version).where(
                        CatalogEntry.namespace == namespace,
                        CatalogEntry.key == key,
                        CatalogEntry.language == language,
                    )
                )
            ).scalar_one_or_none()
            version = int(current or 0) + 1
            values = {
                "namespace": namespace,
                "key": key,
                "language": language,
                "message": message,
                "state": state,
                "catalog_version": version,
                "updated_by": actor.user_id,
                "updated_at": now,
            }
            await uow.session.execute(
                insert(CatalogEntry)
                .values(**values)
                .on_conflict_do_update(constraint="uq_catalog_entries", set_=values)
            )
            await uow.session.flush()
            await self.catalogs.reload_overrides_in(uow.session)
            messages, digest = self.catalogs.bundle(
                namespace, LocaleContext(language=language, fallback_chain=())
            )
            await uow.session.execute(
                insert(CatalogVersion)
                .values(namespace=namespace, language=language, version=digest, published_at=now)
                .on_conflict_do_update(
                    index_elements=["namespace", "language"], set_={"version": digest, "published_at": now}
                )
            )
            published = await self.events.publish(
                uow.session,
                "i18n.translation_updated",
                {"namespace": namespace, "language": language, "catalog_version": digest},
                occurred_at=now,
                actor=actor,
                source="i18n",
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="i18n.translation_updated",
                    actor=actor,
                    resource=ResourceRef("translation", f"{namespace}:{key}:{language}"),
                    decision="allow",
                    result="success",
                    context={"state": state, "catalog_version": version},
                    sensitive=True,
                    event_id=published.event_id,
                ),
            )
        return {
            "namespace": namespace,
            "key": key,
            "language": language,
            "catalog_version": version,
            "version": digest,
            "keys": len(messages),
        }
