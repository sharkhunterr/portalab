"""#316 — self-writing newsletter editions: built-in and own templates; a preview of a template being
written, drawn as an e-mail page (escaped, its palette, its sections in order); a draft published then
e-mailed once; members read the published editions only, framed by the portal; an edition's pictures
answer by its token alone, and only those it shows; an « edition » schedule writes and publishes one."""

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select

from portalab.capabilities.media import DIGEST, EDITION, DigestItem
from portalab.core.time import FixedClock
from portalab.modules.news.models import Category
from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration

POSTER = "0190aaaa-0000-7000-8000-000000000001"
OTHER = "0190aaaa-0000-7000-8000-000000000002"


class _Library:
    def __init__(self, today: date) -> None:
        self.items = [
            DigestItem(
                "Dune <3>",
                "movie",
                (today - timedelta(days=2)).isoformat(),
                "/media/a",
                object_id="0190bbbb-0000-7000-8000-00000000000a",
                picture=POSTER,
                year=2026,
                genres=("Science-fiction",),
                overview="Le désert, encore.",
                rating=8.1,
            ),
            DigestItem("Andor", "series", (today - timedelta(days=1)).isoformat(), "/media/b", "S02E05"),
        ]

    async def releases(self, since: date, until: date, limit: int) -> list[DigestItem]:
        return []

    async def additions(self, since: datetime, limit: int) -> list[DigestItem]:
        return self.items[:limit]

    async def upcoming(self, until: date, limit: int) -> list[DigestItem]:
        return [
            DigestItem("Andor", "series", until.isoformat(), "/media/b", "S03E01"),
            DigestItem("Mickey 17", "movie", until.isoformat(), "/media/c"),
        ]

    async def requests(self, days: int, limit: int) -> list[DigestItem]:
        return [DigestItem("Arcane", "series", "2026-10-30", "/media/d", "approved", picture="t-arcane.jpg")]

    async def period(self, days: int, *, top: int, tz: str = "UTC") -> dict[str, Any]:
        return {
            "totals": {"plays": 42, "seconds": 36_000.0, "members": 5, "works": 12},
            "previous": {"seconds": 30_000.0},
            "by_kind": [
                {"kind": "movie", "plays": 10, "seconds": 20_000.0},
                {"kind": "episode", "plays": 30, "seconds": 16_000.0},
            ],
            "timeline": {"unit": "day", "points": [{"date": "2026-10-30", "seconds": 7200.0}]},
            "weekdays": [0.0, 0.0, 0.0, 3600.0, 7200.0, 0.0, 0.0],
            "hours": [0.0] * 20 + [10_800.0, 0.0, 0.0, 0.0],
            "genres": [{"name": "Science-fiction", "seconds": 9000.0}],
            "top": [{"item": self.items[1], "plays": 9, "seconds": 18_000.0}],
        }

    async def picture(self, image_id: str) -> bytes | None:
        return b"\xff\xd8poster" if image_id in (POSTER, OTHER, "t-arcane.jpg") else None


async def test_editions(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    library = _Library(clock.now().date())
    capabilities = ct.ev.full.identity.capabilities
    capabilities.provide(DIGEST, library, instance_ref="test-editions", owner="test")
    capabilities.provide(EDITION, library, instance_ref="test-editions", owner="test")
    await login(client, "boss")
    await client.put(
        "/api/v1/admin/news/categories",
        json={"key": "lettre", "name": "La lettre", "newsletter": True},
    )
    async with ct.database.session() as session:
        channel = await session.scalar(select(Category).where(Category.key == "lettre"))
    assert channel is not None

    # the built-in templates, then one of the news desk's own (the built-in ones cannot change)
    listed = (await client.get("/api/v1/admin/news/newsletter-templates")).json()
    # #320: Portalab first
    assert [t["key"] for t in listed] == ["portalab", "classic", "midnight", "gazette"]
    classic = listed[1]["definition"]
    assert (
        await client.put("/api/v1/admin/news/newsletter-templates/classic", json=classic)
    ).status_code == 422
    own = {
        **classic,
        "name": "Ma lettre",
        "brand": "Xeno <portal>",
        "palette": {**classic["palette"], "accent": "#123456"},
        "sections": [
            {"kind": "notice"},
            {"kind": "top", "layout": "list", "limit": 3},
            {"kind": "additions", "layout": "grid", "columns": 2, "media": ["movie"]},
        ],
    }
    saved = await client.put("/api/v1/admin/news/newsletter-templates/ma-lettre", json=own)
    assert saved.status_code == 200
    bad = {**own, "palette": {**own["palette"], "text": "red; background:url(x)"}}
    assert (await client.put("/api/v1/admin/news/newsletter-templates/bad", json=bad)).status_code == 422

    # a preview of the template as it is being written
    preview = await client.post(
        "/api/v1/admin/news/newsletter-editions/preview",
        json={"template_key": "ma-lettre", "definition": own, "notice": "Maintenance <samedi>", "days": 7},
    )
    assert preview.status_code == 200 and preview.json()["status"] == "preview"
    page = await client.get(f"/api/v1/admin/news/newsletter-editions/{preview.json()['id']}/page")
    assert page.status_code == 200 and "frame-ancestors 'self'" in page.headers["content-security-policy"]
    html = page.text
    assert "#123456" in html and "Xeno &lt;portal&gt;" in html and "Maintenance &lt;samedi&gt;" in html
    assert "Dune &lt;3&gt;" in html and "<3>" not in html and "Andor" in html  # the top, then the films
    assert html.index("Maintenance") < html.index("Andor") < html.index("Dune")
    assert "Science-fiction" in html and "8.1" in html

    # a draft, then published and e-mailed once to the channel's subscribers
    draft = (
        await client.post(
            "/api/v1/admin/news/newsletter-editions",
            json={"template_key": "classic", "category_id": str(channel.id)},
        )
    ).json()
    assert draft["status"] == "draft"
    await login(client, "rita")
    assert (await client.get("/api/v1/news/editions")).json() == []
    assert (await client.get(f"/api/v1/news/editions/{draft['id']}/page")).status_code == 404
    await login(client, "boss")
    sent = await client.post(
        f"/api/v1/admin/news/newsletter-editions/{draft['id']}/publish", json={"email": True}
    )
    assert sent.json()["status"] == "published" and sent.json()["recipients"] > 0
    again = await client.post(
        f"/api/v1/admin/news/newsletter-editions/{draft['id']}/publish", json={"email": True}
    )
    assert again.status_code == 200
    mails = [r for r in ct.outbox.sent if r.dedup_key == f"news.edition:{draft['id']}"]
    assert len(mails) == 1 and mails[0].email_body is not None
    mail = mails[0].email_body["html"]
    assert "<table" in mail and "Dune &lt;3&gt;" in mail

    # #317: the real e-mail without the members — a test to me alone
    tested = await client.post(f"/api/v1/admin/news/newsletter-editions/{draft['id']}/test")
    assert tested.json() == {"sent": True}
    [test] = [r for r in ct.outbox.sent if r.dedup_key.startswith(f"news.edition-test:{draft['id']}")]
    assert test.audience.ids == (people["boss"],)  # type: ignore[attr-defined]
    assert test.email_body is not None and test.email_body["subject"].startswith("[Test]")
    assert 'src="http' in test.email_body["html"]  # the pictures' whole address, for a mail client

    # the members read it in the portal; its pictures answer by its token, and only its own
    await login(client, "rita")
    assert [e["id"] for e in (await client.get("/api/v1/news/editions")).json()] == [draft["id"]]
    shown = await client.get(f"/api/v1/news/editions/{draft['id']}/page")
    assert shown.status_code == 200 and shown.headers["x-frame-options"] == "SAMEORIGIN"
    start = shown.text.index("/api/v1/newsletters/pictures/")
    address = shown.text[start : shown.text.index('"', start)]
    await client.post("/api/v1/auth/logout")
    anonymous = httpx.AsyncClient(transport=client._transport, base_url=str(client.base_url))
    picture = await anonymous.get(address)
    assert picture.status_code == 200 and picture.content.startswith(b"\xff\xd8")
    assert (await anonymous.get(address.replace(POSTER, OTHER))).status_code == 404
    assert (await anonymous.get(address.replace(address.split("/")[-2], "x" * 43))).status_code == 404

    # an « edition » schedule writes and publishes its edition
    await login(client, "boss")
    schedule = await client.post(
        "/api/v1/admin/news/newsletters",
        json={
            "name": "La lettre du vendredi",
            "category_id": str(channel.id),
            "kind": "edition",
            "template_key": "gazette",
            "cadence": "weekly",
            "weekday": 4,
            "hour": 18,
            "email": False,
        },
    )
    assert schedule.status_code == 201 and schedule.json()["template_key"] == "gazette"
    run = (await client.post(f"/api/v1/admin/news/newsletters/{schedule.json()['id']}/run")).json()
    assert run["article"] is None and run["edition"]
    editions = (await client.get("/api/v1/admin/news/newsletter-editions")).json()
    assert {e["template_key"] for e in editions} == {"classic", "gazette"}
    unknown = {**schedule.json(), "template_key": "nope"}
    for field in ("id", "last_run_at", "next_run_at", "last_article_id"):
        unknown.pop(field, None)
    assert (await client.post("/api/v1/admin/news/newsletters", json=unknown)).status_code == 404


async def test_an_edition_tells_the_contents_switched_on(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    """#323: the contents switched on, in their order, each in the template's manner — the films and the
    series apart, the requests with their state, the TV programme (the series' episodes airing) beside what
    comes soon (the rest); a content switched off is not there."""
    library = _Library(clock.now().date())
    capabilities = ct.ev.full.identity.capabilities
    capabilities.provide(DIGEST, library, instance_ref="test-contents", owner="test")
    capabilities.provide(EDITION, library, instance_ref="test-contents", owner="test")
    await login(client, "boss")
    offered = (await client.get("/api/v1/admin/news/newsletter-contents")).json()
    assert offered["contents"][:3] == ["notice", "stats", "top"] and "tv" in offered["defaults"]
    preview = await client.post(
        "/api/v1/admin/news/newsletter-editions/preview",
        json={"template_key": "gazette", "contents": ["movies", "requests", "tv", "upcoming"], "days": 7},
    )
    assert preview.status_code == 200
    html = (await client.get(f"/api/v1/admin/news/newsletter-editions/{preview.json()['id']}/page")).text
    assert "Dune" in html and "Arcane" in html  # the films, the requests
    assert html.index("Dune") < html.index("Arcane") < html.index("S03E01") < html.index("Mickey 17")
    assert (
        "S02E05" not in html
    )  # the series' arrivals are switched off (Andor shows on the TV programme only)
    assert "La période en chiffres" not in html and "The period in figures" not in html  # no statistics
    bad = await client.post(
        "/api/v1/admin/news/newsletter-editions/preview",
        json={"template_key": "gazette", "contents": ["weather"]},
    )
    assert bad.status_code == 422


async def test_the_statistics_draw_the_charts_switched_on(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    """#324: the statistics as the charts chosen — drawn with cells (no script, no SVG), the peak named —,
    the others left out; the usual ones by default."""
    library = _Library(clock.now().date())
    capabilities = ct.ev.full.identity.capabilities
    capabilities.provide(DIGEST, library, instance_ref="test-charts", owner="test")
    capabilities.provide(EDITION, library, instance_ref="test-charts", owner="test")
    await login(client, "boss")
    offered = (await client.get("/api/v1/admin/news/newsletter-contents")).json()
    assert offered["charts"][0] == "figures" and offered["chart_defaults"] == ["figures", "activity", "kinds"]

    async def page(**ask: Any) -> str:
        made = await client.post(
            "/api/v1/admin/news/newsletter-editions/preview",
            json={"template_key": "portalab", "contents": ["stats"], "language": "fr", **ask},
        )
        assert made.status_code == 200, made.text
        return (await client.get(f"/api/v1/admin/news/newsletter-editions/{made.json()['id']}/page")).text

    chosen = await page(charts=["kinds", "hours"])
    # (the harness speaks in the words' keys)
    assert "edition.chart.kinds" in chosen and "edition.chart.hours" in chosen and "3&nbsp;h" in chosen
    assert (
        "edition.chart.activity" not in chosen and "edition.stats.plays" not in chosen
    )  # nor activity nor figures
    assert "<svg" not in chosen and "<script" not in chosen
    usual = await page()
    assert "edition.chart.activity" in usual and "edition.chart.kinds" in usual
    assert "edition.chart.hours" not in usual
    assert "▲ 20 %" in usual  # the time watched, against the previous period
