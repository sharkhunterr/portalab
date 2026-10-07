"""A title's request journey (027, the media page): from the request to the library, step by step — asked
(by whom, when), approved, released (cinema, digital, physical; a series' first episode), searched by the
download manager (Radarr, Sonarr: followed, monitored, what its history says), downloading (the managers'
queues, completed by the torrent clients — speed, peers, why a transfer does not move), imported (or
waiting for a manual import), available (when it was added, where).

Each step is ``done``, ``current``, ``waiting`` (nothing to do but wait), ``blocked`` (someone must act),
``failed`` or ``upcoming``, with the facts that explain it. The interactive search of the indexers is slow
and loads the indexers: it runs on demand only and its result is kept a while per title."""

import asyncio
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import asdict
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media import (
    ACQUISITION,
    DOWNLOAD_CLIENTS,
    FoundRelease,
    SourceAcquisition,
    SourceDownload,
    TorrentState,
    unwrap,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import strong_ids
from portalab.modules.media.models import MediaRequest, ObjectMetadata
from portalab.modules.media.observability import log

SEARCH_TTL = 30 * 60
SERIES = ("series", "season", "episode")


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value else None


def _step(key: str, status: str, **facts: Any) -> dict[str, Any]:
    return {"key": key, "status": status, **{k: v for k, v in facts.items() if v not in (None, [], {})}}


class RequestJourney:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        catalog: Any,
        insights: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.catalog = catalog
        self.insights = insights
        self.clock = clock
        self._searches: dict[UUID, tuple[float, str | None, list[dict[str, Any]]]] = {}

    def _providers(self, name: str) -> list[Any]:
        try:
            return [r.provider for r in self.capabilities.system_providers(name)]
        except Exception:
            return []

    async def _target(self, viewer: Principal, object_id: UUID) -> tuple[Any, str, dict[str, str]]:
        """The title a download manager knows: a season or an episode is followed through its series."""
        view = await self.catalog.get(viewer, object_id)
        kind, ids, current = view.kind, dict(view.ids), view
        hops = 0
        while current.kind in ("season", "episode") and current.parent_id is not None and hops < 3:
            current = await self.catalog.get(viewer, current.parent_id)
            hops += 1
        if current is not view:
            kind, ids = current.kind, dict(current.ids)
        return view, ("series" if kind in SERIES else kind), ids

    async def _request(self, object_id: UUID, ids: Mapping[str, str]) -> MediaRequest | None:
        wanted = set(strong_ids(ids).items())
        async with self.database.session() as session:
            direct = (
                await session.execute(
                    select(MediaRequest)
                    .where(MediaRequest.object_id == object_id)
                    .order_by(MediaRequest.requested_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if direct is not None or not wanted:
                return direct
            recent = (
                await session.execute(
                    select(MediaRequest).order_by(MediaRequest.requested_at.desc()).limit(500)
                )
            ).scalars()
            for row in recent:
                if wanted & set(strong_ids((row.external_ref or {}).get("ids") or {}).items()):
                    return row
        return None

    async def _requester(self, user: UUID | None, viewer: Principal) -> dict[str, Any] | None:
        if user is None:
            return None
        if user == (viewer.acting_for or viewer.user_id):
            return {"me": True}
        with suppress(Exception):
            directory = self._providers(DIRECTORY)
            if directory:
                summary = await directory[0].get_user_summary(user)
                return {"me": False, "name": summary.display_name if summary else None}
        return {"me": False}

    async def _acquisition(self, kind: str, ids: Mapping[str, str]) -> SourceAcquisition | None:
        if kind not in ("movie", "series") or not ids:
            return None
        results = await asyncio.gather(
            *(asyncio.wait_for(p.status(kind, ids), timeout=12) for p in self._providers(ACQUISITION)),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                log.info("acquisition status unavailable", extra={"reason": type(result).__name__})
                continue
            with suppress(Exception):
                found = unwrap(result)
                if found is not None:
                    return found  # type: ignore[no-any-return]
        return None

    async def _downloads(self, kind: str, ids: Mapping[str, str]) -> list[SourceDownload]:
        wanted = set(strong_ids(ids).items())
        if not wanted:
            return []
        try:
            queue = await self.insights.queue()
        except Exception:
            return []
        # a film and a series may share a TMDB number: a film's downloads are films, a series' episodes
        same = ("movie",) if kind == "movie" else ("episode", "series", "season")
        return [d for d in queue if d.kind in same and wanted & set(strong_ids(d.ids).items())]

    async def _torrents(self, downloads: Sequence[SourceDownload]) -> dict[str, TorrentState]:
        hashes = [d.download_id for d in downloads if d.download_id]
        if not hashes:
            return {}
        results = await asyncio.gather(
            *(asyncio.wait_for(p.torrents(hashes), timeout=10) for p in self._providers(DOWNLOAD_CLIENTS)),
            return_exceptions=True,
        )
        out: dict[str, TorrentState] = {}
        for result in results:
            if isinstance(result, BaseException):
                continue
            with suppress(Exception):
                for torrent in unwrap(result):
                    out[torrent.download_id] = torrent
        return out

    async def _release_date(self, object_id: UUID) -> date | None:
        async with self.database.session() as session:
            raw = await session.scalar(
                select(ObjectMetadata.data["release_date"].astext).where(
                    ObjectMetadata.object_id == object_id, ObjectMetadata.status == "found"
                )
            )
        with suppress(ValueError, TypeError):
            return date.fromisoformat(str(raw)[:10]) if raw else None
        return None

    async def journey(self, viewer: Principal, object_id: UUID) -> dict[str, Any]:
        view, kind, ids = await self._target(viewer, object_id)
        now = utc_now(self.clock)
        request, acquisition, downloads = await asyncio.gather(
            self._request(object_id, ids), self._acquisition(kind, ids), self._downloads(kind, ids)
        )
        torrents = await self._torrents(downloads)
        steps: list[dict[str, Any]] = []
        if request is None and acquisition is None and not downloads:
            # nobody asked for it and no download manager follows it: no journey to tell
            return {
                "kind": kind,
                "available": bool(view.available),
                "request": None,
                "manager": None,
                "history": [],
                "steps": [],
                "can_search": False,
                "search": None,
            }
        available = bool(view.available) or bool(acquisition and acquisition.has_file and kind == "movie")

        # 1. asked, 2. approved
        if request is not None:
            steps.append(
                _step(
                    "requested",
                    "done",
                    at=_iso(request.requested_at),
                    by=await self._requester(request.requester_user_id, viewer),
                )
            )
            if request.state == "pending":
                steps.append(_step("approved", "waiting", detail="pending"))
            elif request.state in ("declined", "cancelled"):
                steps.append(_step("approved", "failed", detail=request.state, at=_iso(request.updated_at)))
            elif request.state == "failed":
                steps.append(_step("approved", "failed", detail="failed", at=_iso(request.updated_at)))
            else:
                steps.append(_step("approved", "done", at=_iso(request.updated_at)))

        # 3. released
        releases = dict(acquisition.releases) if acquisition else {}
        if kind == "movie":
            cinema, digital, physical = (
                releases.get("cinema"),
                releases.get("digital"),
                releases.get("physical"),
            )
            if not releases:
                known = await self._release_date(object_id)
                if known:
                    cinema = datetime(known.year, known.month, known.day, tzinfo=now.tzinfo)
            home = min((d for d in (digital, physical) if d), default=None)
            facts = {"cinema": _iso(cinema), "digital": _iso(digital), "physical": _iso(physical)}
            if available or (home and home <= now) or (acquisition and acquisition.searchable):
                steps.append(_step("released", "done", **facts))
            elif cinema and cinema > now:
                steps.append(_step("released", "waiting", detail="before_cinema", **facts))
            elif cinema:
                steps.append(_step("released", "waiting", detail="in_cinema", **facts))
            elif releases or facts["cinema"]:
                steps.append(_step("released", "waiting", detail="unknown", **facts))
        elif kind == "series" and acquisition:
            first = releases.get("first_aired")
            if first and first > now:
                steps.append(_step("released", "waiting", detail="before_air", first_aired=_iso(first)))
            else:
                steps.append(
                    _step(
                        "released",
                        "done",
                        first_aired=_iso(first),
                        next_airing=_iso(releases.get("next_airing")),
                    )
                )

        # 4. searched by the download manager
        history = [asdict(e) | {"at": _iso(e.at)} for e in (acquisition.history if acquisition else ())]
        if acquisition is None:
            if request is not None and request.state in ("approved", "processing") and not available:
                steps.append(_step("searched", "blocked", detail="not_tracked"))
        elif not acquisition.monitored and not available:
            steps.append(
                _step("searched", "blocked", detail="not_monitored", manager=acquisition.service_name)
            )
        elif downloads or available or acquisition.has_file:
            steps.append(_step("searched", "done", manager=acquisition.service_name))
        else:
            ready = steps[-1]["status"] == "done" if steps and steps[-1]["key"] == "released" else True
            failed = next((e for e in history if e["event"] == "failed"), None)
            steps.append(
                _step(
                    "searched",
                    "current" if ready else "upcoming",
                    detail="no_release" if ready else "after_release",
                    manager=acquisition.service_name,
                    last_failure=failed,
                )
            )

        # 5. downloading, 6. imported
        if downloads:
            items: list[dict[str, Any]] = []
            for d in downloads:
                torrent = torrents.get(d.download_id or "")
                items.append(
                    {
                        "title": d.title,
                        "season": d.season,
                        "episode": d.episode,
                        "status": d.status,
                        "progress": d.progress,
                        "eta": _iso(d.eta),
                        "client": d.client or (torrent.client if torrent else None),
                        "release": d.release,
                        "attention": d.attention,
                        "messages": list(d.messages),
                        "size": d.size,
                        "torrent": {
                            "state": torrent.state,
                            "progress": torrent.progress,
                            "speed": torrent.download_speed,
                            "eta_s": torrent.eta_s,
                            "seeds": torrent.seeds,
                            "peers": torrent.peers,
                        }
                        if torrent
                        else None,
                    }
                )
            blocked = [i for i in items if i["attention"] in ("import_blocked", "failed", "warning")]
            importing = [i for i in items if i["status"] == "importing" and not i["attention"]]
            fetching = [i for i in items if i["status"] != "importing"]
            if fetching:
                stuck = any(
                    (i["torrent"] or {}).get("state") in ("stalled", "metadata", "error", "paused")
                    for i in fetching
                )
                steps.append(
                    _step(
                        "downloading",
                        "blocked"
                        if stuck and not any(i["status"] == "downloading" for i in fetching)
                        else "current",
                        progress=round(sum(i["progress"] for i in fetching) / len(fetching), 3),
                        items=fetching,
                    )
                )
            else:
                steps.append(_step("downloading", "done"))
            if blocked:
                failed_import = any(i["attention"] == "failed" for i in blocked)
                steps.append(
                    _step(
                        "imported",
                        "failed" if failed_import else "blocked",
                        detail="failed" if failed_import else "manual",
                        items=blocked,
                    )
                )
            elif importing:
                steps.append(_step("imported", "current", items=importing))
            else:
                steps.append(_step("imported", "upcoming"))
        elif acquisition is not None or request is not None:
            done = available or (acquisition is not None and acquisition.has_file)
            grabbed = next((e for e in history if e["event"] == "grabbed"), None)
            imported = next((e for e in history if e["event"] == "imported"), None)
            steps.append(_step("downloading", "done" if done else "upcoming", at=(grabbed or {}).get("at")))
            steps.append(_step("imported", "done" if done else "upcoming", at=(imported or {}).get("at")))

        # 7. in the library
        if available:
            added = None
            if acquisition is not None:
                last_import = next((e for e in acquisition.history if e.event == "imported"), None)
                added = last_import.at if last_import else acquisition.added_at
            steps.append(
                _step(
                    "available",
                    "done",
                    at=_iso(view.first_seen_at or added),
                    files=acquisition.files if acquisition else None,
                    expected=acquisition.expected if acquisition and kind == "series" else None,
                    quality=acquisition.quality if acquisition else None,
                    size=acquisition.size if acquisition else None,
                )
            )
        elif steps:
            steps.append(_step("available", "upcoming"))

        cached = self._searches.get(object_id)
        return {
            "kind": kind,
            "available": available,
            "request": {
                "state": request.state,
                "source_state": request.source_state,
                "requested_at": _iso(request.requested_at),
                "updated_at": _iso(request.updated_at),
                "by": await self._requester(request.requester_user_id, viewer),
            }
            if request is not None
            else None,
            "manager": {  # 027: no link to the download manager — members have no use for it
                "name": acquisition.service_name,
                "monitored": acquisition.monitored,
                "status": acquisition.status,
                "added_at": _iso(acquisition.added_at),
                "files": acquisition.files,
                "expected": acquisition.expected,
                "quality": acquisition.quality,
                "size": acquisition.size,
            }
            if acquisition is not None
            else None,
            "history": history[:8],
            "steps": steps,
            "can_search": acquisition is not None and not available,
            "search": {"at": cached[1], "releases": cached[2]}
            if cached and time.time() - cached[0] < SEARCH_TTL
            else None,
        }

    async def search(self, viewer: Principal, object_id: UUID) -> dict[str, Any]:
        """The download managers' interactive search for this title (kept 30 minutes)."""
        cached = self._searches.get(object_id)
        if cached and time.time() - cached[0] < SEARCH_TTL:
            return {"at": cached[1], "releases": cached[2]}
        _, kind, ids = await self._target(viewer, object_id)
        found: list[FoundRelease] = []
        for provider in self._providers(ACQUISITION):
            try:
                result = unwrap(await asyncio.wait_for(provider.search(kind, ids), timeout=90))
            except Exception as exc:
                log.info("interactive search unavailable", extra={"reason": type(exc).__name__})
                continue
            found.extend(result or [])
        releases = [asdict(r) | {"rejections": list(r.rejections)} for r in found][:30]
        at = _iso(utc_now(self.clock))
        self._searches[object_id] = (time.time(), at, releases)
        return {"at": at, "releases": releases}
