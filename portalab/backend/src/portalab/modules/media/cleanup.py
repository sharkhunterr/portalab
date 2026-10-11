"""#57: the cleanup tool's deletions (Maintainerr), seen from the portal.

What its rules will delete is read from the ``media.cleanup`` providers (kept five minutes) and tied to
the catalog — by the media server's id of the item (a Plex rating key is the library's own id), else by
a strong id of the same kind. A title page says when it goes; a member who bought a *rescue* in the shop
spends it to save the title (a global exclusion in the cleanup tool: no rule takes it again). The rescues
are a ledger: credited by the shop (``purchase``, idempotent per purchase), spent per title (``rescue``,
one per title — whoever saves it saves it for everyone).
"""

import asyncio
import time
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.media import CLEANUP, LIBRARY, LeavingItem, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Conflict, Unavailable
from portalab.core.time import Clock, utc_now
from portalab.modules.media.identity.resolver import MediaNotFound
from portalab.modules.media.models import MediaObject, RescueLedger, SourceItem
from portalab.modules.media.observability import log, metrics
from portalab.modules.media.requests.service import known_title

TTL = 300.0
TIMEOUT = 20.0
SAME_KIND = {"movie": ("movie",), "series": ("series",), "season": ("season",), "episode": ("episode",)}


@dataclass(frozen=True, slots=True)
class Leaving:
    object_id: UUID
    item: LeavingItem
    provider: Any


class NoRescue(Conflict):
    default_code = "media.no_rescue"
    default_title = "No rescue left"


class CleanupService:
    def __init__(self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None):
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self._cache: tuple[float, list[Leaving]] | None = None
        self._lock = asyncio.Lock()

    def _providers(self) -> list[Any]:
        try:
            return [r.provider for r in self.capabilities.system_providers(CLEANUP)]
        except Exception:
            return []

    def configured(self) -> bool:
        return bool(self._providers())

    def forget(self) -> None:
        self._cache = None

    # --- what goes ------------------------------------------------------------------------------------
    async def leaving(self) -> list[Leaving]:
        async with self._lock:
            if self._cache and time.monotonic() - self._cache[0] < TTL:
                return self._cache[1]
            found = await self._fetch()
            self._cache = (time.monotonic(), found)
            return found

    async def _fetch(self) -> list[Leaving]:
        providers = self._providers()
        results = await asyncio.gather(
            *(asyncio.wait_for(p.leaving(), timeout=TIMEOUT) for p in providers), return_exceptions=True
        )
        pairs: list[tuple[Any, LeavingItem]] = []
        for provider, result in zip(providers, results, strict=True):
            if isinstance(result, BaseException):
                log.info("cleanup list unavailable", extra={"reason": type(result).__name__})
                continue
            with suppress(Exception):
                pairs.extend((provider, item) for item in unwrap(result))
        if not pairs:
            return []
        async with self.database.session() as session:
            by_id = await self._library_ids(session, [item.external_id for _, item in pairs])
            saved = set(
                (
                    await session.execute(
                        select(RescueLedger.object_id).where(
                            RescueLedger.reason == "rescue", RescueLedger.object_id.is_not(None)
                        )
                    )
                ).scalars()
            )
            out: list[Leaving] = []
            for provider, item in pairs:
                object_id = next(
                    (o for o, kind in by_id.get(item.external_id, ()) if kind in SAME_KIND[item.kind]), None
                )
                if object_id is None and item.kind in ("movie", "series") and item.ids:
                    object_id = await known_title(session, item.ids, item.kind)
                if object_id is not None and object_id not in saved:
                    out.append(Leaving(object_id, item, provider))
        metrics.gauge("media.cleanup.leaving", len(out))
        return out

    async def _library_ids(
        self, session: AsyncSession, external_ids: Sequence[str]
    ) -> dict[str, list[tuple[UUID, str]]]:
        """The catalog titles behind the media servers' ids (each with its kind)."""
        rows = await session.execute(
            select(SourceItem.external_id, SourceItem.object_id, MediaObject.kind)
            .join(MediaObject, MediaObject.id == SourceItem.object_id)
            .where(
                SourceItem.capability == LIBRARY,
                SourceItem.external_id.in_(sorted(set(external_ids))[:5000]),
            )
        )
        out: dict[str, list[tuple[UUID, str]]] = {}
        for external_id, object_id, kind in rows:
            out.setdefault(external_id, []).append((object_id, kind))
        return out

    async def _for_object(self, session: AsyncSession, object_id: UUID) -> list[tuple[Leaving, str]]:
        """What goes of this title: itself, or its seasons (with each one's title)."""
        children = {
            row.id: row.title
            for row in (
                await session.execute(select(MediaObject).where(MediaObject.parent_id == object_id))
            ).scalars()
        }
        own = await session.get(MediaObject, object_id)
        names = {object_id: own.title if own else "", **children}
        return [(entry, names[entry.object_id]) for entry in await self.leaving() if entry.object_id in names]

    # --- rescues --------------------------------------------------------------------------------------
    async def credits(self, user: UUID) -> int:
        async with self.database.session() as session:
            return await self._balance(session, user)

    @staticmethod
    async def _balance(session: AsyncSession, user: UUID) -> int:
        total = await session.scalar(
            select(func.coalesce(func.sum(RescueLedger.delta), 0)).where(RescueLedger.user_id == user)
        )
        return max(0, int(total or 0))

    async def grant(self, user: UUID, count: int, source_ref: str) -> int:
        """The shop credits rescues (``RescueCredits``) — once per purchase."""
        async with self.database.unit_of_work() as uow:
            session = uow.session
            exists = await session.scalar(
                select(RescueLedger.id).where(RescueLedger.source_ref == source_ref)
            )
            if exists is None and count > 0:
                session.add(
                    RescueLedger(
                        user_id=user,
                        delta=min(int(count), 100),
                        reason="purchase",
                        source_ref=source_ref[:200],
                        created_at=utc_now(self.clock),
                    )
                )
                await session.flush()
            return await self._balance(session, user)

    async def status(self, object_id: UUID, user: UUID) -> dict[str, Any]:
        async with self.database.session() as session:
            entries = await self._for_object(session, object_id)
            rescue = (
                await session.execute(
                    select(RescueLedger)
                    .where(RescueLedger.object_id == object_id, RescueLedger.reason == "rescue")
                    .order_by(RescueLedger.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            credits = await self._balance(session, user)
        dates = [e.item.delete_at for e, _ in entries if e.item.delete_at]
        return {
            "configured": self.configured(),
            "leaving": [
                {
                    "kind": entry.item.kind,
                    "title": title,
                    "collection": entry.item.collection,
                    "added_at": entry.item.added_at.isoformat(),
                    "delete_at": _iso(entry.item.delete_at),
                    "size": entry.item.size,
                }
                for entry, title in entries
            ],
            "delete_at": _iso(min(dates)) if dates else None,
            # whoever saved it saved it for everyone — the portal says when, and whether it was me
            "saved": {"at": rescue.created_at.isoformat(), "me": rescue.user_id == user} if rescue else None,
            "credits": credits,
        }

    async def keep(self, object_id: UUID, user: UUID) -> dict[str, Any]:
        """Spend one rescue: the cleanup tool excludes the title (and its leaving seasons) for good."""
        async with self.database.unit_of_work() as uow:
            session = uow.session
            # one member's rescues are spent one at a time (two clicks never spend two)
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"media.rescue:{user}"}
            )
            entries = await self._for_object(session, object_id)
            if not entries:
                raise MediaNotFound("This title is not scheduled for deletion.", code="media.not_leaving")
            if await self._balance(session, user) <= 0:
                raise NoRescue("You have no rescue left: buy one in the shop.")
            for entry, _ in entries:
                try:
                    await asyncio.wait_for(entry.provider.keep(entry.item.external_id), timeout=TIMEOUT)
                except Exception as exc:
                    log.warning("cleanup exclusion failed", extra={"reason": type(exc).__name__})
                    raise Unavailable(
                        "The cleanup tool did not take the rescue: try again later.",
                        code="media.cleanup_unavailable",
                    ) from exc
            now = utc_now(self.clock)
            own = await session.get(MediaObject, object_id)
            # one rescue spent for the title; its seasons that were going are marked saved with it
            saved = {object_id: own.title if own else None}
            saved.update({e.object_id: t for e, t in entries if e.object_id != object_id})
            for saved_id, title in saved.items():
                session.add(
                    RescueLedger(
                        user_id=user,
                        delta=-1 if saved_id == object_id else 0,
                        reason="rescue",
                        source_ref=f"rescue:{saved_id}:{now.timestamp():.0f}",
                        object_id=saved_id,
                        title=title[:500] if title else None,
                        created_at=now,
                    )
                )
        self.forget()
        metrics.increment("media.cleanup.rescued")
        return await self.status(object_id, user)

    async def soonest(self, limit: int = 12) -> list[dict[str, Any]]:
        """The widget's titles: the first to go first (those without a date last), one card per title."""
        entries = await self.leaving()
        firsts: dict[UUID, Leaving] = {}
        for entry in entries:
            known = firsts.get(entry.object_id)
            if known is None or _key(entry) < _key(known):
                firsts[entry.object_id] = entry
        ordered = sorted(firsts.values(), key=_key)[:limit]
        async with self.database.session() as session:
            objects = {
                o.id: o
                for o in (
                    await session.execute(
                        select(MediaObject).where(MediaObject.id.in_([e.object_id for e in ordered]))
                    )
                ).scalars()
            }
        return [
            {
                "id": str(entry.object_id),
                "title": objects[entry.object_id].title,
                "kind": objects[entry.object_id].kind,
                "delete_at": _iso(entry.item.delete_at),
                "collection": entry.item.collection,
            }
            for entry in ordered
            if entry.object_id in objects
        ]


def _key(entry: Leaving) -> tuple[int, datetime]:
    at = entry.item.delete_at
    return (0, at) if at else (1, entry.item.added_at)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
