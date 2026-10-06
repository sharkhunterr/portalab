"""Media releases in the portal calendar (027): the films and episodes the library services (Radarr,
Sonarr…) expect, as all-day ``publication`` items of kind ``media_release`` — read through ``Upcoming``
(cached, a failing service is skipped)."""

from datetime import datetime
from typing import Any

from portalab.capabilities.content import CalendarItem, CalendarSourceResult
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import utc_now
from portalab.modules.media.insights.upcoming import Upcoming

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

    def _item(self, release: dict[str, Any]) -> CalendarItem:
        at = datetime.fromisoformat(release["at"])
        object_id = release.get("object_id")
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
        )

    async def items(
        self, start: datetime, end: datetime, viewer: Principal, ctx: LocaleContext
    ) -> CalendarSourceResult:
        try:
            releases = await self.upcoming.list(HORIZON_DAYS)
        except Exception:
            return CalendarSourceResult(state="unavailable", as_of=utc_now(self.upcoming.clock))
        lower, upper = start.isoformat(), end.isoformat()
        return CalendarSourceResult(
            items=[self._item(r) for r in releases if lower <= r["at"] <= upper],
            as_of=utc_now(self.upcoming.clock),
        )

    async def item(self, source_id: str, viewer: Principal) -> CalendarItem | None:
        for release in await self.upcoming.list(HORIZON_DAYS):
            candidate = self._item(release)
            if candidate.source_id == source_id:
                return candidate
        return None
