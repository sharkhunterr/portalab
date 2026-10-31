"""Issue 229: ``media.card_sources`` — what the cards are made of. The films and series of the catalog that a
metadata provider (TMDB) knows: their credits in their order, their votes, countries, languages, saga and
artwork (references served by ``/media/metadata-images``), and the work a played object belongs to."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select

from portalab.capabilities.media import METADATA, VIDEO_FRAMES, unwrap
from portalab.capabilities.media_core import CardImage, CardPerson, CardWork
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.modules.media.models import MediaObject, ObjectMetadata, SourceItem

KINDS = ("movie", "series")
# the crew a card is made for, by their job
CREW = {
    "Director": "director",
    "Creator": "creator",
    "Screenplay": "writer",
    "Writer": "writer",
    "Original Music Composer": "composer",
}


def _people(raw: Any) -> list[CardPerson]:
    out: list[CardPerson] = []
    cast = 0
    for person in raw if isinstance(raw, list) else []:
        if not isinstance(person, Mapping) or not person.get("name"):
            continue
        name = str(person["name"])[:120]
        tmdb = (person.get("ids") or {}).get("tmdb")
        ref = f"tmdb:{tmdb}" if tmdb else f"name:{name.lower()}"
        image = person.get("image") if isinstance(person.get("image"), str) else None
        if person.get("department") == "cast":
            out.append(CardPerson(ref, name, "cast", person.get("role") or None, cast, image))
            cast += 1
        elif (category := CREW.get(str(person.get("role") or ""))) is not None:
            out.append(CardPerson(ref, name, category, str(person["role"]), 0, image))
    return out


def _year(data: Mapping[str, Any], fallback: int | None) -> int | None:
    released = str(data.get("release_date") or "")
    return int(released[:4]) if released[:4].isdigit() else fallback


def _strings(raw: Any) -> list[str]:
    return [str(v) for v in raw if isinstance(v, str)] if isinstance(raw, list) else []


def _facts(data: Mapping[str, Any]) -> dict[str, Any]:
    """The figures a work's cards print: budget, revenue (dollars), runtime (minutes), seasons, director."""
    out: dict[str, Any] = {}
    for key, name in (
        ("budget", "budget"),
        ("revenue", "revenue"),
        ("runtime_min", "runtime"),
        ("seasons", "seasons"),
    ):
        value = data.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
            out[name] = int(value)
    director = next(
        (
            str(p["name"])[:120]
            for p in data.get("people") or []
            if isinstance(p, Mapping) and p.get("role") in ("Director", "Creator") and p.get("name")
        ),
        None,
    )
    if director:
        out["director"] = director
    return out


class MediaCardSources:
    def __init__(
        self, database: Database, capabilities: CapabilityRegistry | None = None, enricher: Any = None
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.enricher = enricher

    async def image(self, ref: str, size: str) -> bytes:
        """A metadata image (cached in the blob store by the enricher)."""
        if self.enricher is None:
            raise LookupError("no metadata images")
        data: bytes = await self.enricher.image(ref, size)
        return data

    async def works(self, *, since: datetime | None = None) -> Sequence[CardWork]:
        query = (
            select(MediaObject, ObjectMetadata)
            .join(ObjectMetadata, ObjectMetadata.object_id == MediaObject.id)
            .where(
                MediaObject.kind.in_(KINDS),
                MediaObject.status == "active",
                MediaObject.merged_into.is_(None),
                ObjectMetadata.status == "found",
            )
        )
        if since is not None:
            query = query.where(or_(ObjectMetadata.fetched_at > since, MediaObject.updated_at > since))
        async with self.database.session() as session:
            rows = (await session.execute(query)).all()
        out: list[CardWork] = []
        for item, meta in rows:
            data = meta.data or {}
            out.append(
                CardWork(
                    object_id=item.id,
                    kind=item.kind,
                    title=str(data.get("title") or item.title)[:200],
                    year=_year(data, item.year),
                    countries=_strings(data.get("countries")),
                    languages=_strings(data.get("languages")),
                    vote_count=int(data.get("vote_count") or 0),
                    vote_average=float(data["vote_average"]) if data.get("vote_average") else None,
                    tagline=str(data["tagline"])[:300] if data.get("tagline") else None,
                    poster=data.get("poster") if isinstance(data.get("poster"), str) else None,
                    backdrop=data.get("backdrop") if isinstance(data.get("backdrop"), str) else None,
                    backdrops=_strings(data.get("backdrops")),
                    collection=data.get("collection")
                    if isinstance(data.get("collection"), Mapping)
                    else None,
                    people=_people(data.get("people")),
                    updated_at=max(item.updated_at, meta.fetched_at),
                    available=bool(item.available),
                    tmdb=str(tmdb) if (tmdb := (data.get("ids") or {}).get("tmdb")) else None,
                    ids={str(k): str(v) for k, v in (data.get("ids") or {}).items() if v},
                    genres=_strings(data.get("genres")),
                    facts=_facts(data),
                    overview=str(data["overview"])[:1200] if data.get("overview") else None,
                    keywords=_strings(data.get("keywords")),
                )
            )
        return out

    async def present(self) -> Sequence[UUID]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(MediaObject.id).where(
                            MediaObject.kind.in_(KINDS),
                            MediaObject.status == "active",
                            MediaObject.merged_into.is_(None),
                        )
                    )
                ).scalars()
            )

    async def work_of(self, object_id: UUID) -> UUID | None:
        """The film itself, or the series an episode (or a season) belongs to."""
        async with self.database.session() as session:
            current = await session.get(MediaObject, object_id)
            for _ in range(3):
                if current is None:
                    return None
                if current.kind in KINDS:
                    return current.id
                current = await session.get(MediaObject, current.parent_id) if current.parent_id else None
        return None

    async def season_of(self, object_id: UUID) -> int | None:
        """Issue 234: a season's number (``None``: not a season)."""
        async with self.database.session() as session:
            item = await session.get(MediaObject, object_id)
        return item.position if item is not None and item.kind == "season" else None

    async def role_images(self, person_ref: str) -> Sequence[CardImage] | None:
        """Issue 229: the images a person is tagged in (their characters), from the metadata provider that
        can tell (TMDB); ``None`` when none can."""
        if self.capabilities is None or not person_ref.startswith("tmdb:"):
            return None
        for registration in self.capabilities.system_providers(METADATA):
            tagged = getattr(registration.provider, "role_images", None)
            if tagged is None:
                continue
            found = unwrap(await tagged(person_ref.removeprefix("tmdb:")))
            return [CardImage(i.media_id, i.image, i.image_type, i.aspect, i.votes) for i in found or []]
        return None

    async def frames(self, object_id: UUID, at: Sequence[float]) -> Sequence[bytes] | None:
        """Issue 230: still images of a film's own video, from a media server holding its file that can take
        them (Plex); ``None`` when none can, an empty list when the film's file gives none."""
        if self.capabilities is None:
            return None
        providers = {r.instance_ref: r.provider for r in self.capabilities.system_providers(VIDEO_FRAMES)}
        if not providers:
            return None
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(SourceItem.service_id, SourceItem.external_id)
                    .where(
                        SourceItem.object_id == object_id,
                        SourceItem.active.is_(True),
                        SourceItem.kind == "movie",
                    )
                    .order_by(SourceItem.last_seen_at.desc())
                )
            ).all()
        for service_id, external_id in rows:
            provider = providers.get(str(service_id))
            if provider is not None:
                return [image async for image in provider.frames(external_id, list(at))]
        return None
