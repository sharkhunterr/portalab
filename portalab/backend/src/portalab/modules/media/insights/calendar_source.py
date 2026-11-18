"""Media releases in the portal calendar (027): the films and episodes the library services (Radarr,
Sonarr…) expect, as all-day ``publication`` items of kind ``media_release`` — read through ``Upcoming``
(cached, a failing service is skipped). Issue 502: with its title's poster when the library has it."""

from datetime import datetime
from typing import Any
from uuid import UUID

from portalab.capabilities.content import CalendarItem, CalendarSourceResult
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import utc_now
from portalab.modules.media.insights.upcoming import Upcoming
from portalab.modules.media.providers.insight_widgets import posters

HORIZON_DAYS = 90
CATEGORY = {"movie": "movie", "episode": "series", "series": "series", "book": "book", "audiobook": "book"}


def _title(release: dict[str, Any]) -> str:
    if release.get("parent_title") and release.get("episode") is not None:
        return f"{release['parent_title']} S{release.get('season') or 0:02d}E{release['episode']:02d}"
    return str(release.get("parent_title") or release.get("title") or "")


class MediaReleaseCalendarSource:
    kind = "media_release"
    label_key = "calendar:source.media_release"

    def __init__(self, upcoming: Upcoming) -> None:
        self.upcoming = upcoming

    def _item(self, release: dict[str, Any], images: dict[UUID, str] | None = None) -> CalendarItem:
        at = datetime.fromisoformat(release["at"])
        object_id = release.get("object_id")
        image = (images or {}).get(UUID(object_id)) if object_id else None
        return CalendarItem(
            source_kind=self.kind,
            source_id=f"{release.get('kind')}:{_title(release)}:{at.date().isoformat()}",
            type="publication",
            title=_title(release),
            date=at.date(),
            all_day=True,
            status="available" if release.get("available") else "scheduled",
            url_ref=f"/media/{object_id}" if object_id else "/media/insights",
            category=CATEGORY.get(str(release.get("kind") or ""), "movie"),
            image=f"/api/v1/media/images/{image}" if image else None,
        )

    async def _posters(self, releases: list[dict[str, Any]]) -> dict[UUID, str]:
        try:
            return await posters(
                self.upcoming.database, (UUID(r["object_id"]) for r in releases if r.get("object_id"))
            )
        except Exception:  # a release without its poster is still told
            return {}

    async def items(
        self, start: datetime, end: datetime, viewer: Principal, ctx: LocaleContext
    ) -> CalendarSourceResult:
        try:
            releases = await self.upcoming.list(HORIZON_DAYS)
        except Exception:
            return CalendarSourceResult(state="unavailable", as_of=utc_now(self.upcoming.clock))
        lower, upper = start.isoformat(), end.isoformat()
        shown = [r for r in releases if lower <= r["at"] <= upper]
        images = await self._posters(shown)
        return CalendarSourceResult(
            items=[self._item(r, images) for r in shown],
            as_of=utc_now(self.upcoming.clock),
        )

    async def item(self, source_id: str, viewer: Principal) -> CalendarItem | None:
        for release in await self.upcoming.list(HORIZON_DAYS):
            candidate = self._item(release)
            if candidate.source_id == source_id:
                return self._item(release, await self._posters([release]))
        return None
