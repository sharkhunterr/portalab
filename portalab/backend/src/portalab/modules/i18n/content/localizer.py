"""Multilingual content registry (T031; R11, FR-014..016, FR-032). Content domains keep their texts in
their own tables; this registry records, per ``(kind, id)``, which language versions exist and in which
state (``source`` / ``translated`` / ``untranslated`` / ``machine_draft``). The source version is immutable
(database trigger); a translation is a new version. ``get`` returns the version for the user's language,
or the source/fallback version flagged ``is_fallback`` — never rewriting anything."""

from dataclasses import dataclass

from sqlalchemy import func, select

from portalab.capabilities.i18n import ContentState, LocaleContext, LocalizedContent
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.i18n.models import LocalizedContentVersion


@dataclass(frozen=True, slots=True)
class ContentKind:
    kind: str
    read_permission: str
    owner: str


class ContentKinds:
    """Owning modules register their content kinds with the permission that guards reading them."""

    def __init__(self) -> None:
        self._kinds: dict[str, ContentKind] = {}

    def register(self, kind: ContentKind) -> None:
        self._kinds[kind.kind] = kind

    def get(self, kind: str) -> ContentKind | None:
        return self._kinds.get(kind)

    def unregister(self, owner: str) -> int:
        doomed = [k for k, v in self._kinds.items() if v.owner == owner]
        for k in doomed:
            del self._kinds[k]
        return len(doomed)


default_content_kinds = ContentKinds()


class ContentLocalizer:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def register_version(
        self,
        content_kind: str,
        content_id: str,
        language: str,
        *,
        state: ContentState,
        source_language: str,
        translation_of_version: int | None = None,
    ) -> int:
        if state != "source" and translation_of_version is None:
            raise ValidationFailed("A translation must reference the source version it translates.")
        async with self.database.unit_of_work() as uow:
            current = await uow.session.scalar(
                select(func.max(LocalizedContentVersion.version)).where(
                    LocalizedContentVersion.content_kind == content_kind,
                    LocalizedContentVersion.content_id == content_id,
                    LocalizedContentVersion.language == language,
                )
            )
            version = int(current or 0) + 1
            uow.session.add(
                LocalizedContentVersion(
                    content_kind=content_kind,
                    content_id=content_id,
                    language=language,
                    source_language=source_language,
                    state=state,
                    translation_of_version=translation_of_version,
                    version=version,
                    created_at=utc_now(self.clock),
                )
            )
        return version

    async def get(self, content_kind: str, content_id: str, ctx: LocaleContext) -> LocalizedContent | None:
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(LocalizedContentVersion)
                        .where(
                            LocalizedContentVersion.content_kind == content_kind,
                            LocalizedContentVersion.content_id == content_id,
                        )
                        .order_by(LocalizedContentVersion.version.desc())
                    )
                )
                .scalars()
                .all()
            )
        if not rows:
            return None
        latest: dict[str, LocalizedContentVersion] = {}
        for row in rows:
            latest.setdefault(row.language, row)
        usable = {lang: row for lang, row in latest.items() if row.state in ("source", "translated")}
        for language in (ctx.language, *ctx.fallback_chain):
            found = usable.get(language)
            if found is not None:
                return _out(found, is_fallback=language != ctx.language)
        source = next((row for row in latest.values() if row.state == "source"), rows[0])
        return _out(source, is_fallback=True)


def _out(row: LocalizedContentVersion, *, is_fallback: bool) -> LocalizedContent:
    return LocalizedContent(
        content_kind=row.content_kind,
        content_id=row.content_id,
        language=row.language,
        version=row.version,
        state=row.state,  # type: ignore[arg-type]
        is_fallback=is_fallback,
        source_language=row.source_language,
    )
