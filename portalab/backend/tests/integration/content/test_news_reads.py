"""#48 — who read what: opening a published article is remembered once; the listing, the featured news
and the widget say which ones this member has not read; the editors see who read it and who has not;
a member's reads are exported with their data and erased with them."""

from uuid import UUID

import httpx
import pytest

from portalab.capabilities.i18n import LocaleContext
from portalab.modules.news.articles import ArticleInput
from portalab.modules.news.integrations import NewsWidget
from portalab.modules.news.participant import NewsParticipant
from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_reads(client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID]) -> None:
    articles = ct.news.articles
    boss = ct.p("boss")
    first = await articles.create(boss, ArticleInput("First", "one"))
    second = await articles.create(boss, ArticleInput("Second", "two"))
    draft = await articles.create(boss, ArticleInput("Draft", "three"))
    for row in (first, second):
        await articles.transition(boss, row.id, "publish")
    await articles.feature(boss, draft.id, None, None, 0)  # featured before it is published

    await login(client, "rita")
    unread = {i["title"]: i["unread"] for i in (await client.get("/api/v1/news")).json()["items"]}
    assert unread == {"First": True, "Second": True}
    for _ in range(2):
        assert (await client.post(f"/api/v1/news/{first.slug}/read")).status_code == 204
    assert (await client.post(f"/api/v1/news/{draft.slug}/read")).status_code == 404  # not hers to see
    unread = {i["title"]: i["unread"] for i in (await client.get("/api/v1/news")).json()["items"]}
    assert unread == {"First": False, "Second": True}

    widget = await NewsWidget(articles, featured=False).load(ct.p("rita"), {}, LocaleContext())
    assert widget.data is not None and widget.data["unread"] == 1

    shown = await articles.readers(boss, first.id)
    assert [r["user_id"] for r in shown["read"]] == [str(people["rita"])]
    assert str(people["rita"]) not in [r["user_id"] for r in shown["unread"]]
    counts = await articles.read_counts([first.id, second.id])
    assert counts == {first.id: 1}

    participant = NewsParticipant(ct.database)
    exported = await participant.export(people["rita"])
    assert [r.data["title"] for r in exported if r.category == "news.read"] == ["First"]
    await participant.erase(people["rita"], "final")
    assert await articles.read_counts([first.id]) == {}
