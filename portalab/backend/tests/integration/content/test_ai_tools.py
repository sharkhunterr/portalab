"""Issue 171 — the assistant's announcements and wiki tools, as the member it acts for: the published
announcements newest first (a draft never), optionally matching words; a wiki page by its address or title —
its text only when its editors let the assistant read it, never a page the member may not see."""

from uuid import UUID

import pytest

from portalab.core.authz_port import Principal
from portalab.modules.news.ai_tools import NewsAiTools
from portalab.modules.news.articles import ArticleInput
from portalab.modules.wiki.ai_tools import WikiAiTools
from portalab.modules.wiki.pages import PageInput
from tests.integration.content.conftest import ContentHarness

pytestmark = pytest.mark.integration


async def test_announcements_and_wiki_pages(ct: ContentHarness, people: dict[str, UUID]) -> None:
    boss = ct.p("boss")
    rita = Principal(channel="ai", acting_for=people["rita"])
    articles = ct.news.articles
    first = await articles.create(boss, ArticleInput("Maintenance on Sunday", "The server restarts at 8."))
    second = await articles.create(boss, ArticleInput("New films added", "Twelve new films."))
    await articles.create(boss, ArticleInput("Secret draft", "not yet"))
    for row in (first, second):
        await articles.transition(boss, row.id, "publish")
    [latest] = NewsAiTools(articles).tools()
    found = await latest.handler(rita, {})
    assert {a["title"] for a in found.data["announcements"]} == {"Maintenance on Sunday", "New films added"}
    assert all(s.url.startswith("/news/") for s in found.sources)
    one = await latest.handler(rita, {"query": "maintenance"})
    assert [a["title"] for a in one.data["announcements"]] == ["Maintenance on Sunday"]

    pages = ct.wiki.pages
    await pages.create(
        boss,
        PageInput("Request a film", "Open **Discover**, find it, press Request.", readable_by_ai=True),
        publish=True,
    )
    await pages.create(boss, PageInput("Private notes", "staff only", readable_by_ai=False), publish=True)
    await pages.create(
        boss,
        PageInput("Runbook", "admins", readable_by_ai=True, audience={"mode": "roles", "refs": ["admin"]}),
        publish=True,
    )
    [page] = WikiAiTools(pages).tools()
    read = await page.handler(rita, {"page": "request a film"})
    assert read.data["found"] and "press Request" in read.data["text"] and read.data["cut"] is False
    assert read.sources[0].source_class == "knowledge" and read.sources[0].url.startswith("/wiki/")
    slug = read.sources[0].url.removeprefix("/wiki/")
    assert (await page.handler(rita, {"page": f"/wiki/{slug}"})).data["title"] == "Request a film"
    closed = await page.handler(rita, {"page": "Private notes"})
    assert closed.data["readable"] is False and "text" not in closed.data and not closed.sources
    assert (await page.handler(rita, {"page": "Runbook"})).data == {"found": False, "page": "Runbook"}
    assert (await page.handler(rita, {"page": "Nothing here"})).data["found"] is False
