"""027 — newsletters: a channel (category) may be e-mailed; publishing one of its articles e-mails it once to
every member except those who unsubscribed from that channel, with the article itself as the e-mail;
members manage their channels; a schedule writes its newsletter from what the media services report
(nothing written when there is nothing to tell) and plans its next run."""

from datetime import date, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select

from portalab.capabilities.media import DIGEST, DigestItem
from portalab.capabilities.notifications import Users
from portalab.core.time import FixedClock
from portalab.modules.news.articles import ArticleInput
from portalab.modules.news.models import Category
from portalab.modules.news.newsletters import next_run
from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


class _Digest:
    def __init__(self) -> None:
        self.items: list[DigestItem] = []

    async def releases(self, since: date, until: date, limit: int) -> list[DigestItem]:
        return [i for i in self.items if since.isoformat() <= i.date <= until.isoformat()][:limit]

    async def additions(self, since: datetime, limit: int) -> list[DigestItem]:
        return self.items[:limit]

    async def upcoming(self, until: date, limit: int) -> list[DigestItem]:
        return []


async def test_newsletters(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    await login(client, "boss")
    channel = await client.put(
        "/api/v1/admin/news/categories",
        json={"key": "films", "name": "Sorties films", "newsletter": True, "description": "Chaque semaine"},
    )
    assert channel.status_code == 200 and channel.json()["newsletter"] is True
    async with ct.database.session() as session:
        films = await session.scalar(select(Category).where(Category.key == "films"))
    assert films is not None

    await login(client, "rita")
    mine = (await client.get("/api/v1/me/newsletters")).json()
    assert [(c["key"], c["subscribed"]) for c in mine] == [("films", True)]
    changed = await client.put("/api/v1/me/newsletters", json={"changes": {"films": False}})
    assert changed.status_code == 200 and changed.json()[0]["subscribed"] is False
    assert (await client.put("/api/v1/me/newsletters", json={"changes": {"nope": True}})).status_code == 422

    articles = ct.news.articles
    eddie = ct.p("eddie")
    draft = await articles.create(
        eddie,
        ArticleInput(
            "Dune 3 arrive",
            "Un **grand** film : [voir](/media/x)",
            category_id=films.id,
            email_on_publish=True,
        ),
    )
    await articles.transition(ct.p("boss"), draft.id, "publish")
    [request] = [r for r in ct.outbox.sent if r.category == "news.newsletter"]
    assert isinstance(request.audience, Users)
    assert people["rita"] not in request.audience.ids and people["eddie"] in request.audience.ids
    assert request.email_body is not None and "<strong>grand</strong>" in request.email_body["html"]
    assert request.email_body["subject"] == "Dune 3 arrive"
    # published again (archived, restored, republished): never e-mailed twice
    await articles.transition(ct.p("boss"), draft.id, "archive")
    assert len([r for r in ct.outbox.sent if r.category == "news.newsletter"]) == 1

    # an automatic newsletter: nothing to tell → no article; then the week's releases
    digest = _Digest()
    ct.ev.full.identity.capabilities.provide(DIGEST, digest, instance_ref="test", owner="test")
    await login(client, "boss")
    created = await client.post(
        "/api/v1/admin/news/newsletters",
        json={
            "name": "Sorties de la semaine",
            "category_id": str(films.id),
            "kind": "releases",
            "cadence": "weekly",
            "weekday": 4,
            "hour": 18,
            "language": "fr",
        },
    )
    assert created.status_code == 201 and created.json()["next_run_at"] is not None
    schedule = created.json()["id"]
    empty = await client.post(f"/api/v1/admin/news/newsletters/{schedule}/run")
    assert empty.json() == {"article": None, "edition": None}
    today = clock.now().date()
    digest.items = [
        DigestItem("Dune 3", "movie", (today - timedelta(days=2)).isoformat(), "/media/a"),
        DigestItem("Andor", "series", (today - timedelta(days=1)).isoformat(), "/media/b", "S02E05"),
    ]
    written = (await client.post(f"/api/v1/admin/news/newsletters/{schedule}/run")).json()["article"]
    assert written["status"] == "published" and written["email_on_publish"] is True
    body = written["body_md"]  # films first, then series (the wording comes from the i18n catalog)
    assert body.count("### ") == 2 and body.index("Dune 3") < body.index("Andor")
    assert "[**Andor**](/media/b)" in body
    assert "S02E05" in written["body_md"]
    listed = (await client.get("/api/v1/admin/news/newsletters")).json()
    assert listed[0]["last_article_id"] == written["id"]


def test_next_run() -> None:
    from zoneinfo import ZoneInfo

    paris = ZoneInfo("Europe/Paris")
    monday = datetime(2026, 10, 5, 12, tzinfo=paris)
    friday = next_run("weekly", 4, 18, monday, paris)
    assert friday.astimezone(paris) == datetime(2026, 10, 9, 18, tzinfo=paris)
    assert next_run("daily", 0, 9, monday, paris).astimezone(paris) == datetime(2026, 10, 6, 9, tzinfo=paris)
    first = next_run("monthly", 0, 9, monday, paris).astimezone(paris)
    assert first == datetime(2026, 11, 2, 9, tzinfo=paris)  # the first Monday of next month


async def test_newsletters_switched_off(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID]
) -> None:
    """Issue 246: switched off, the newsletters answer nothing, members read no channel, nothing is sent."""
    from portalab.core.authz_port import Principal
    from portalab.modules.administration.config.service import Change

    config = ct.ev.full.administration.config
    await config.apply(
        [Change("news.newsletter.enabled", False)], Principal(user_id=people["boss"]), reason="t"
    )
    await login(client, "boss")
    off = await client.get("/api/v1/admin/news/newsletters")
    assert off.status_code == 404 and off.json()["code"] == "news.newsletters_off"
    assert (await client.put("/api/v1/me/newsletters", json={"changes": {}})).status_code == 404
    assert (await client.get("/api/v1/me/newsletters")).json() == []
    assert await ct.news.newsletters.run_due() == 0
    await config.apply(
        [Change("news.newsletter.enabled", True)], Principal(user_id=people["boss"]), reason="t"
    )
    assert (await client.get("/api/v1/admin/news/newsletters")).status_code == 200
