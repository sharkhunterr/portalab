"""011 T023/T026/T028/T030 — the calendar merges items from its sources (news publications, maintenance,
fakes) with per-source states (a slow or failing source degrades only itself), applies permission at the
source, caps the range; reminders fire once through ``notifications.send`` and re-check the item (moved ⇒
rescheduled with a notice, removed ⇒ cancelled), are erased with the account; domains link to each other
through ``ContentRef`` with per-viewer states; translations show the user's language or say they are
missing."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.content import CalendarItem, CalendarSourceResult
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.health.calendar_source import MaintenanceCalendarSource
from portalab.modules.news.articles import ArticleInput
from portalab.modules.wiki.pages import PageInput
from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


@dataclass
class FakeSource:
    kind: str
    label_key: str = "test:source"
    items_: dict[str, CalendarItem] = field(default_factory=dict)
    delay: float = 0.0
    fail: bool = False
    hidden_from: set[UUID] = field(default_factory=set)

    async def items(
        self, start: datetime, end: datetime, viewer: Principal, ctx: LocaleContext
    ) -> CalendarSourceResult:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise ConnectionError("source down")
        visible = [i for i in self.items_.values() if viewer.user_id not in self.hidden_from]
        return CalendarSourceResult(items=visible)

    async def item(self, source_id: str, viewer: Principal) -> CalendarItem | None:
        if viewer.user_id in self.hidden_from:
            return None
        return self.items_.get(source_id)


def event(kind: str, source_id: str, title: str, at: datetime, **extra: object) -> CalendarItem:
    return CalendarItem(
        source_kind=kind, source_id=source_id, type="event", title=title, starts_at=at, **extra
    )  # type: ignore[arg-type]


async def test_aggregation(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    now = clock.now()
    events = FakeSource(
        "community", items_={"e1": event("community", "e1", "Movie night", now + timedelta(days=1))}
    )
    slow = FakeSource("campaigns", delay=5)
    broken = FakeSource("deadlines", fail=True)
    private = FakeSource(
        "secret", items_={"s": event("secret", "s", "Hidden", now)}, hidden_from={people["rita"]}
    )
    for source in (events, slow, broken, private):
        ct.sources.register(source, owner="test")  # type: ignore[arg-type]
    ct.sources.register(MaintenanceCalendarSource(ct.database, clock=clock), owner="module:health")
    async with ct.database.unit_of_work() as uow:
        await uow.session.execute(
            text(
                "INSERT INTO health.maintenance_windows (id, title, description, starts_at, ends_at, status,"
                " schedule_version, created_at)"
                " VALUES (gen_random_uuid(), 'DB upgrade', '', :s, :e, 'scheduled', 1, now())"
            ),
            {"s": now + timedelta(days=2), "e": now + timedelta(days=2, hours=1)},
        )
    article = await ct.news.articles.create(ct.p("boss"), ArticleInput("Launch", "x"))
    await ct.news.articles.transition(
        ct.p("boss"), article.id, "schedule", publish_at=now + timedelta(days=3)
    )
    ct.calendar.config = __import__("dataclasses").replace(ct.calendar.config, source_timeout_ms=300)
    await login(client, "rita")
    params = {"from": now.isoformat(), "to": (now + timedelta(days=7)).isoformat()}
    view = (await client.get("/api/v1/calendar", params=params)).json()
    assert view["source_states"] == {
        "campaigns": "unavailable", "community": "ok", "deadlines": "unavailable", "maintenance": "ok",
        "news": "ok", "secret": "ok",
    }  # fmt: skip
    assert [i["title"] for i in view["items"]] == [
        "Movie night",
        "DB upgrade",
    ]  # no hidden, no scheduled news
    await login(client, "eddie")
    titles = [i["title"] for i in (await client.get("/api/v1/calendar", params=params)).json()["items"]]
    assert "Launch" in titles and "Hidden" in titles
    too_wide = await client.get(
        "/api/v1/calendar", params={"from": now.isoformat(), "to": (now + timedelta(days=400)).isoformat()}
    )
    assert too_wide.status_code == 422 and too_wide.json()["code"] == "calendar.range_too_large"


async def test_reminders(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    now = clock.now()
    source = FakeSource(
        "community", items_={"e1": event("community", "e1", "Movie night", now + timedelta(hours=3))}
    )
    ct.sources.register(source, owner="test")  # type: ignore[arg-type]
    await login(client, "rita")
    created = await client.post(
        "/api/v1/me/calendar/reminders",
        json={"source_kind": "community", "source_id": "e1", "lead_minutes": 60},
    )
    assert created.status_code == 201
    again = await client.post(
        "/api/v1/me/calendar/reminders",
        json={"source_kind": "community", "source_id": "e1", "lead_minutes": 60},
    )
    assert again.status_code == 409
    reminder = created.json()["id"]
    reminders = ct.calendar.reminders
    assert await reminders.fire({"reminder": reminder}) == "early"
    # the event moves one hour later: the reminder follows, the user is told
    source.items_["e1"] = event("community", "e1", "Movie night", now + timedelta(hours=4))
    clock.advance(timedelta(hours=2, minutes=1))
    assert await reminders.fire({"reminder": reminder}) == "updated"
    assert await reminders.fire({"reminder": reminder}) == "early"
    clock.advance(timedelta(hours=1))
    assert await reminders.fire({"reminder": reminder}) == "sent"
    assert await reminders.fire({"reminder": reminder}) == "sent"  # duplicate job run: no second message
    templates = [r.template_key for r in ct.outbox.sent]
    assert templates == ["calendar:notify.updated", "calendar:notify.reminder"]
    # removed (or no longer visible) at fire time ⇒ cancelled
    source.items_["e2"] = event("community", "e2", "Quiz", clock.now() + timedelta(hours=2))
    second = await reminders.create(people["rita"], "community", "e2", 15)
    source.hidden_from.add(people["rita"])
    clock.advance(timedelta(hours=2))
    assert await reminders.fire({"reminder": str(second.id)}) == "cancelled"
    listed = (await client.get("/api/v1/me/calendar/reminders")).json()
    assert sorted(r["status"] for r in listed) == ["cancelled", "sent"]
    from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY

    participant = next(
        p.provider
        for p in ct.ev.full.identity.capabilities.system_providers(ERASURE_CAPABILITY)
        if p.instance_ref == "calendar"
    )
    await participant.erase(people["rita"], "delete")
    assert (await client.get("/api/v1/me/calendar/reminders")).json() == []


async def test_interconnection_and_translations(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID]
) -> None:
    boss = ct.p("boss")
    private = await ct.wiki.pages.create(
        boss, PageInput("Runbook", "x", audience={"mode": "roles", "refs": ["admin"]}), publish=True
    )
    guide = await ct.wiki.pages.create(boss, PageInput("Guide", "y"), publish=True)
    article = await ct.news.articles.create(
        boss,
        ArticleInput(
            "Hello", f"See [guide](portalab://wiki/{guide.slug}) and [runbook](portalab://wiki/{private.id})"
        ),
    )
    await ct.news.articles.transition(boss, article.id, "publish")
    await ct.news.articles.translate(boss, article.id, "fr", "Bonjour", "", "Voir le guide")
    await login(client, "rita")
    body = (await client.get(f"/api/v1/news/{article.slug}")).json()
    refs = [
        r
        for r in ("portalab://wiki/" + guide.slug, f"portalab://wiki/{private.id}")
        if f'data-ref="{r}"' in body["html"]
    ]
    states = (await client.post("/api/v1/content/links/resolve", json={"refs": refs})).json()
    assert [(s["state"], s["title"]) for s in states] == [("ok", "Guide"), ("forbidden", None)]
    french = (await client.get(f"/api/v1/news/{article.slug}", params={"lang": "fr"})).json()
    assert (
        french["title"] == "Bonjour"
        and french["is_translation"] is True
        and french["source_language"] == "en"
    )
    german = (await client.get(f"/api/v1/news/{article.slug}", params={"lang": "de"})).json()
    assert german["title"] == "Hello" and german["translation_missing"] is True
    await ct.wiki.pages.translate(boss, guide.id, "fr", "Guide FR", "z")
    page = (await client.get(f"/api/v1/wiki/pages/{guide.slug}", params={"lang": "fr"})).json()
    assert page["title"] == "Guide FR" and page["is_translation"] is True
    # one domain's lifecycle does not touch the other: archiving the guide degrades the link only
    await ct.wiki.pages.set_status(boss, guide.id, "archived")
    states = (await client.post("/api/v1/content/links/resolve", json={"refs": refs[:1]})).json()
    assert (
        states[0]["state"] == "archived"
        and (await client.get(f"/api/v1/news/{article.slug}")).status_code == 200
    )
