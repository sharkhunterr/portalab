"""Issue 265: ``media.game_sources`` — what the games page draws from beyond the works the cards are made of:
a series' theme music from the media server that holds it (the blind test), the library's games (RomM: the
week's challenge) and how long each member played one since a moment (its play sessions)."""

import io
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from PIL import Image, ImageFilter
from sqlalchemy import ColumnElement, func, select

from portalab.capabilities.media import THEMES, SourceUnavailable, unwrap
from portalab.capabilities.media_core import PlayableGame, SeenWork
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.modules.media.models import Activity, MediaObject, SourceItem, UserProgress
from portalab.modules.media.providers.insight_widgets import posters
from portalab.modules.media.taste.features import not_a_game


class MediaGameSources:
    def __init__(
        self, database: Database, capabilities: CapabilityRegistry | None = None, enricher: Any = None
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.enricher = enricher

    async def blurred(self, ref: str, radius: int) -> bytes:
        """A scene of a work blurred on the server (the games: the page never holds it sharp before the
        answer)."""
        if self.enricher is None:
            raise LookupError("no metadata images")
        raw: bytes = await self.enricher.image(ref, "w780")
        with Image.open(io.BytesIO(raw)) as source:
            image = source.convert("RGB")
            if radius > 0:
                image = image.filter(ImageFilter.GaussianBlur(radius))
            out = io.BytesIO()
            image.save(out, "JPEG", quality=82)
        return out.getvalue()

    async def theme(self, object_id: UUID) -> bytes | None:
        """A series' theme music, from a media server holding the series that keeps one (Plex)."""
        if self.capabilities is None:
            return None
        providers = {r.instance_ref: r.provider for r in self.capabilities.system_providers(THEMES)}
        if not providers:
            return None
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(SourceItem.service_id, SourceItem.external_id)
                    .where(
                        SourceItem.object_id == object_id,
                        SourceItem.active.is_(True),
                        SourceItem.kind == "series",
                    )
                    .order_by(SourceItem.last_seen_at.desc())
                )
            ).all()
        for service_id, external_id in rows:
            provider = providers.get(str(service_id))
            if provider is not None:
                try:  # a connector's answer comes wrapped (available or not)
                    found: bytes | None = unwrap(await provider.theme(external_id))
                except SourceUnavailable:
                    found = None
                if found:
                    return found
        return None

    async def _titles(self, where: Sequence[ColumnElement[bool]], limit: int) -> list[PlayableGame]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        MediaObject.id,
                        MediaObject.kind,
                        MediaObject.title,
                        MediaObject.year,
                        MediaObject.effective["platform"].astext,
                    )
                    .where(
                        MediaObject.status == "active",
                        MediaObject.parent_id.is_(None),
                        MediaObject.merged_into.is_(None),
                        *where,
                    )
                    # a title of a franchise or a series first (Mario, Metroid…): known to the household
                    .order_by(MediaObject.effective["series"].astext.is_(None), func.random())
                    .limit(limit * 2)
                )
            ).all()
        rows = [r for r in rows if r[1] != "game" or not not_a_game(r[2])][:limit]
        images = await posters(self.database, [r[0] for r in rows])
        return [
            PlayableGame(
                object_id=i,
                title=title,
                platform=platform if kind == "game" else None,
                image_id=UUID(images[i]) if i in images else None,
                year=year,
                kind=kind,
            )
            for i, kind, title, year, platform in rows
        ]

    async def titles(self, kind: str, *, limit: int) -> Sequence[PlayableGame]:
        """Titles of a kind present in the library, at random (the dumps' demos and hacks left out)."""
        return await self._titles([MediaObject.kind == kind, MediaObject.available.is_(True)], limit)

    async def title(self, object_id: UUID) -> PlayableGame | None:
        found = await self._titles([MediaObject.id == object_id], 1)
        return found[0] if found else None

    async def progress(self, kind: str, object_id: UUID, since: datetime) -> Mapping[UUID, float]:
        """A game: seconds each member played it since ``since``. Anything else: how far each went (0 to 1),
        by their services' history and the portal's player and reader."""
        async with self.database.session() as session:
            if kind == "game":
                rows = (
                    await session.execute(
                        select(Activity.user_id, func.sum(Activity.watched_s))
                        .where(
                            Activity.kind == "game",
                            Activity.work_id == object_id,
                            Activity.user_id.is_not(None),
                            Activity.counted.is_(True),
                            Activity.started_at >= since,
                        )
                        .group_by(Activity.user_id)
                    )
                ).all()
                return {user: float(seconds or 0) for user, seconds in rows if user is not None}
            heard = (
                await session.execute(
                    select(Activity.user_id, func.max(Activity.progress))
                    .where(
                        (Activity.work_id == object_id) | (Activity.object_id == object_id),
                        Activity.user_id.is_not(None),
                        Activity.started_at >= since,
                    )
                    .group_by(Activity.user_id)
                )
            ).all()
            kept = (
                await session.execute(
                    select(UserProgress.user_id, UserProgress.percent).where(
                        UserProgress.object_id == object_id, UserProgress.last_occurred_at >= since
                    )
                )
            ).all()
        out: dict[UUID, float] = {}
        shares = [(who, share) for who, share in heard] + [(who, share) for who, share in kept]
        for who, share in shares:
            if who is not None and share is not None:
                out[who] = max(out.get(who, 0.0), float(share))
        return out

    async def seen(self, user: UUID, *, limit: int) -> Sequence[SeenWork]:
        """The works a member's services say they watched, read or played (an episode: its series), the
        latest first."""
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        MediaObject.id,
                        MediaObject.kind,
                        MediaObject.title,
                        MediaObject.year,
                        func.max(Activity.started_at),
                    )
                    .join(MediaObject, MediaObject.id == Activity.work_id)
                    .where(Activity.user_id == user, Activity.counted.is_(True))
                    .group_by(MediaObject.id, MediaObject.kind, MediaObject.title, MediaObject.year)
                    .order_by(func.max(Activity.started_at).desc())
                    .limit(limit)
                )
            ).all()
        return [SeenWork(i, kind, title, year, at) for i, kind, title, year, at in rows if at is not None]
