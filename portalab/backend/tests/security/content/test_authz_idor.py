"""011 T031 — drafts, scheduled and audience-restricted content are unreachable through ids, slugs,
assets, search, featured, calendar, link resolution and help; editorial and history operations are
enforced server-side; sensitive actions are audited; knowledge ports are bounded by the asking principal."""

from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.core.time import FixedClock
from portalab.modules.news.articles import ArticleInput
from portalab.modules.wiki.pages import PageInput
from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_idor_and_enforcement(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    boss = ct.p("boss")
    draft = await ct.news.articles.create(boss, ArticleInput("Secret draft", "x"))
    scheduled = await ct.news.articles.create(boss, ArticleInput("Secret scheduled", "x"))
    await ct.news.articles.transition(
        boss, scheduled.id, "schedule", publish_at=clock.now() + timedelta(days=1)
    )
    restricted = await ct.news.articles.create(
        boss, ArticleInput("Admins only", "x", audience={"mode": "roles", "refs": ["admin"]})
    )
    await ct.news.articles.transition(boss, restricted.id, "publish")
    await ct.news.articles.feature(boss, restricted.id, None, None, 1)
    wiki_draft = await ct.wiki.pages.create(
        boss, PageInput("Wiki draft", "secret", help_keys=["k"], readable_by_ai=True)
    )
    await login(client, "rita")
    for key in (draft.slug, str(draft.id), scheduled.slug, restricted.slug, str(restricted.id)):
        assert (await client.get(f"/api/v1/news/{key}")).status_code == 404, key
    assert (await client.get(f"/api/v1/wiki/pages/{wiki_draft.slug}")).status_code == 404
    assert (await client.get("/api/v1/news/featured")).json() == []
    assert (await client.get("/api/v1/help", params={"key": "k"})).json() == []
    assert await ct.wiki.knowledge.search("secret", ct.p("rita"), for_ai=True) == []
    calendar = await client.get(
        "/api/v1/calendar",
        params={"from": clock.now().isoformat(), "to": (clock.now() + timedelta(days=7)).isoformat()},
    )
    assert "Secret scheduled" not in calendar.text
    links = (
        await client.post(
            "/api/v1/content/links/resolve",
            json={
                "refs": [
                    f"portalab://news/{draft.id}",
                    f"portalab://news/{restricted.slug}",
                    f"portalab://wiki/{wiki_draft.id}",
                ]
            },
        )
    ).json()
    assert all(link["state"] == "forbidden" and link["title"] is None for link in links)
    # editorial operations are refused server-side to readers
    for method, path, body in (
        ("POST", "/api/v1/admin/news/articles", {"title": "x"}),
        ("POST", f"/api/v1/admin/news/articles/{draft.id}/publish", None),
        ("POST", f"/api/v1/admin/news/articles/{restricted.id}/lifecycle/archive", None),
        ("POST", "/api/v1/wiki/pages", {"title": "x", "body_md": "y"}),
        ("POST", f"/api/v1/wiki/pages/{wiki_draft.id}/delete", {}),
        ("GET", f"/api/v1/wiki/pages/{wiki_draft.id}/revisions", None),
        ("PUT", "/api/v1/admin/news/categories", {"key": "x", "name": "X"}),
    ):
        response = await client.request(method, path, json=body)
        assert response.status_code in (403, 404), (path, response.status_code)
    # sensitive editorial actions are audited
    await login(client, "boss")
    await client.post(f"/api/v1/admin/news/articles/{restricted.id}/lifecycle/archive")
    async with ct.database.session() as session:
        audited = (
            (await session.execute(text("SELECT action FROM audit.audit_entries WHERE action LIKE 'news.%'")))
            .scalars()
            .all()
        )
    assert "news.archive" in audited
