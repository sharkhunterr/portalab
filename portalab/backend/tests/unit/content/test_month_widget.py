"""027 — the calendar widget: each entry with its first and last day in the viewer's time zone (an event over
several days becomes one bar), the media release's category (movie, series…), and what comes next."""

from datetime import UTC, date, datetime
from typing import Any

from portalab.capabilities.content import CalendarItem
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.calendar.aggregator import CalendarView
from portalab.modules.calendar.module import MonthWidget

NOW = datetime(2026, 10, 6, 10, tzinfo=UTC)


class _Aggregator:
    async def view(self, viewer: Any, start: datetime, end: datetime, ctx: Any) -> CalendarView:
        return CalendarView(
            items=[
                CalendarItem(
                    source_kind="community_event",
                    source_id="e1",
                    type="community_event",
                    title="Festival",
                    starts_at=datetime(2026, 10, 7, 18, tzinfo=UTC),
                    ends_at=datetime(2026, 10, 9, 22, 0, tzinfo=UTC),  # Paris: 10 Oct, 0:00 — ends on the 9th
                ),
                CalendarItem(
                    source_kind="media_release",
                    source_id="r1",
                    type="publication",
                    title="Andor S02E01",
                    date=date(2026, 10, 12),
                    all_day=True,
                    category="series",
                    url_ref="/media/x",
                ),
                CalendarItem(
                    source_kind="maintenance",
                    source_id="m1",
                    type="maintenance",
                    title="Past",
                    starts_at=datetime(2026, 10, 1, 8, tzinfo=UTC),
                    ends_at=datetime(2026, 10, 1, 9, tzinfo=UTC),
                ),
            ],
            source_states={"community_event": "ok"},
            as_of=NOW,
        )


async def test_entries_span_their_days_in_the_viewer_zone() -> None:
    widget = MonthWidget(_Aggregator(), FixedClock(NOW))  # type: ignore[arg-type]
    payload = await widget.load(Principal(), {"show": "all"}, LocaleContext(time_zone="Europe/Paris"))
    assert payload.data is not None
    entries = {e["title"]: e for e in payload.data["entries"]}
    assert (entries["Festival"]["date"], entries["Festival"]["end"]) == ("2026-10-07", "2026-10-09")
    assert entries["Andor S02E01"]["category"] == "series" and entries["Andor S02E01"]["route"] == "/media/x"
    assert payload.data["today"] == "2026-10-06" and payload.data["month"] == "2026-10-01"
    assert [e["title"] for e in payload.data["upcoming"]] == [
        "Festival",
        "Andor S02E01",
    ]  # the past is not next
    media_only = await widget.load(Principal(), {"show": "media"}, LocaleContext())
    assert [e["title"] for e in media_only.data["entries"]] == ["Andor S02E01"]  # type: ignore[index]
