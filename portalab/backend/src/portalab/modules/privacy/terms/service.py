"""Terms of use (027): the administrators publish versions, every member accepts the one in force.

Optional: with nothing published, or with the switch off (``set_enabled``), the portal asks nothing.

A version is published once and never changed (``terms_versions`` is append-only); a new one supersedes it.
A version that ``requires_acceptance`` (the default — a typo fix may opt out) asks every member to accept it
again: until they do, the portal and the services it opens stay closed to them (``must_accept``, checked on
every API call — cached, so it costs nothing while the member is up to date). Publishing counts as the
publisher's own acceptance. Acceptances are the member's data: exported, erased with the account.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.content.render import render_markdown
from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.privacy.models import TermsAcceptance, TermsSettings, TermsVersion

CACHE_SECONDS = 30.0
TERMS_LOCK = 0x7465726D73  # pg advisory lock: two publications never take the same number


class TermsOutdated(Conflict):
    default_code = "terms.outdated"
    default_title = "A newer version of the terms is in force"


@dataclass(frozen=True, slots=True)
class TermsStatus:
    """Where a member stands: the version in force, the last one they accepted, whether they must act."""

    current: TermsVersion | None
    accepted_version: int | None
    accepted_at: datetime | None
    required: bool


@dataclass(frozen=True, slots=True)
class TermsHistoryEntry:
    version: TermsVersion
    acceptances: int


class TermsService:
    def __init__(self, database: Database, audit: AuditSink, *, clock: Clock | None = None) -> None:
        self.database = database
        self.audit = audit
        self.clock = clock
        self._required: tuple[float, int | None] | None = None  # (fetched at, version members must accept)
        self._accepted: dict[UUID, int] = {}  # member → highest accepted version (only ever grows)

    # --- reading ------------------------------------------------------------------------------------

    async def current(self) -> TermsVersion | None:
        async with self.database.session() as session:
            found: TermsVersion | None = await session.scalar(
                select(TermsVersion).order_by(TermsVersion.version.desc()).limit(1)
            )
        return found

    async def version(self, number: int) -> TermsVersion:
        async with self.database.session() as session:
            found = await session.scalar(select(TermsVersion).where(TermsVersion.version == number))
        if found is None:
            raise NotFound("No such version of the terms.", code="terms.not_found")
        return found

    async def required_version(self) -> int | None:
        """The latest version members must have accepted (``None``: no terms published)."""
        cached = self._required
        if cached is not None and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        async with self.database.session() as session:
            settings = await session.get(TermsSettings, 1)
            number = (
                await session.scalar(
                    select(func.max(TermsVersion.version)).where(TermsVersion.requires_acceptance.is_(True))
                )
                if settings is None or settings.enabled
                else None
            )
        self._required = (time.monotonic(), number)
        return number

    async def enabled(self) -> bool:
        """Whether the administrators ask for the terms (on by default; nothing asked before publishing)."""
        async with self.database.session() as session:
            settings = await session.get(TermsSettings, 1)
        return settings is None or settings.enabled

    async def set_enabled(self, actor: Principal, enabled: bool) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(TermsSettings)
                .values(id=1, enabled=enabled, updated_at=utc_now(self.clock))
                .on_conflict_do_update(
                    index_elements=[TermsSettings.id],
                    set_={"enabled": enabled, "updated_at": utc_now(self.clock)},
                )
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="privacy.terms_enforcement",
                    actor=actor,
                    resource=ResourceRef("terms", "settings"),
                    decision="allow",
                    result="success",
                    context={"enabled": enabled},
                    sensitive=True,
                ),
            )
        self._required = None

    async def _accepted_version(self, user_id: UUID) -> tuple[int | None, datetime | None]:
        async with self.database.session() as session:
            row = (
                await session.execute(
                    select(TermsAcceptance.version, TermsAcceptance.accepted_at)
                    .where(TermsAcceptance.user_id == user_id)
                    .order_by(TermsAcceptance.version.desc())
                    .limit(1)
                )
            ).first()
        return (row[0], row[1]) if row else (None, None)

    async def must_accept(self, user_id: UUID) -> bool:
        required = await self.required_version()
        if required is None:
            return False
        known = self._accepted.get(user_id)
        if known is not None and known >= required:
            return False
        accepted, _ = await self._accepted_version(user_id)
        if accepted is not None:
            self._accepted[user_id] = accepted
        return accepted is None or accepted < required

    async def status(self, user_id: UUID) -> TermsStatus:
        current = await self.current() if await self.enabled() else None
        accepted, at = await self._accepted_version(user_id)
        required = await self.must_accept(user_id)
        return TermsStatus(current, accepted, at, required)

    async def history(self) -> Sequence[TermsHistoryEntry]:
        async with self.database.session() as session:
            versions = list(
                (await session.execute(select(TermsVersion).order_by(TermsVersion.version.desc()))).scalars()
            )
            rows = await session.execute(
                select(TermsAcceptance.version, func.count()).group_by(TermsAcceptance.version)
            )
            counts: dict[int, int] = {int(v): int(n) for v, n in rows}
        return [TermsHistoryEntry(v, int(counts.get(v.version, 0))) for v in versions]

    async def up_to_date(self) -> int:
        """How many members accepted the version in force (or a later one)."""
        required = await self.required_version()
        if required is None:
            return 0
        async with self.database.session() as session:
            count = await session.scalar(
                select(func.count(func.distinct(TermsAcceptance.user_id))).where(
                    TermsAcceptance.version >= required
                )
            )
        return int(count or 0)

    # --- acting -------------------------------------------------------------------------------------

    async def accept(self, user_id: UUID, version: int) -> TermsStatus:
        """The member accepts ``version`` — only the version in force (they read what they accept)."""
        current = await self.current()
        if current is None or current.version != version:
            raise TermsOutdated("Only the terms in force can be accepted; read them again.")
        await self._record(user_id, version)
        return await self.status(user_id)

    async def _record(self, user_id: UUID, version: int) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(TermsAcceptance)
                .values(user_id=user_id, version=version, accepted_at=utc_now(self.clock))
                .on_conflict_do_nothing()
            )
        self._accepted[user_id] = max(version, self._accepted.get(user_id, 0))

    async def publish(
        self, actor: Principal, *, title: str, summary: str, body_md: str, requires_acceptance: bool
    ) -> TermsVersion:
        title, body_md = title.strip(), body_md.strip()
        if not title or not body_md:
            raise ValidationFailed("The terms need a title and a text.", code="terms.empty")
        rendered = render_markdown(body_md)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(select(func.pg_advisory_xact_lock(TERMS_LOCK)))  # one at a time
            last = await uow.session.scalar(select(func.max(TermsVersion.version)))
            if last is None:
                requires_acceptance = True  # the first terms always ask to be accepted
            published = TermsVersion(
                version=(last or 0) + 1,
                title=title[:200],
                summary=summary.strip()[:1000],
                body_md=body_md,
                body_html=rendered.html,
                requires_acceptance=requires_acceptance,
                published_at=utc_now(self.clock),
            )
            uow.session.add(published)
            await uow.session.flush()
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="privacy.terms_published",
                    actor=actor,
                    resource=ResourceRef("terms", str(published.version)),
                    decision="allow",
                    result="success",
                    context={"version": published.version, "requires_acceptance": requires_acceptance},
                    sensitive=True,
                ),
            )
        self._required = None
        if actor.user_id is not None:  # publishing is the publisher's own acceptance
            await self._record(actor.user_id, published.version)
        return published


class TermsParticipant:
    """Privacy participant: a member's acceptances are exported with their data and erased with them."""

    def __init__(self, terms: TermsService) -> None:
        self.terms = terms

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.terms.database.session() as session:
            rows = await session.execute(
                select(TermsAcceptance.version, TermsAcceptance.accepted_at)
                .where(TermsAcceptance.user_id == user_id)
                .order_by(TermsAcceptance.version)
            )
            return [
                ExportRecord("privacy.terms_acceptance", {"version": v, "accepted_at": at.isoformat()})
                for v, at in rows
            ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.terms.database.unit_of_work() as uow:
            await uow.session.execute(delete(TermsAcceptance).where(TermsAcceptance.user_id == user_id))
        self.terms._accepted.pop(user_id, None)
