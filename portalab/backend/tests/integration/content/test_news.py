"""011 T017/T018/T021/T034 — news lifecycle: valid transitions only; drafts invisible to readers; a
scheduled article is published exactly once at ``publish_at`` even when the job runs twice; featuring
window, cap and order; archive leaves discovery but stays readable by link; deleting needs care;
audience enforced on list/detail/featured/search and on notifications (one communication per audience
target, deduplicated on replay); the ``content.publish`` action runs as its author."""

from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.notifications import AllAuthenticated, Role
from portalab.capabilities.search.testkit import query
from portalab.core.time import FixedClock
from portalab.modules.news.articles import PUBLISH_JOB, ArticleInput, InvalidTransition
from tests.authz_fixtures import automation
from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_lifecycle_and_schedule(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    articles = ct.news.articles
    eddie = ct.p("eddie")
    draft = await articles.create(
        eddie, ArticleInput("Release 2.0", "**New**", summary="What's new", notify_on_publish=True)
    )
    await login(client, "rita")
    assert (await client.get(f"/api/v1/news/{draft.slug}")).status_code == 404
    assert (await client.get("/api/v1/news")).json()["items"] == []
    with pytest.raises(InvalidTransition):
        await articles.transition(eddie, draft.id, "archive")  # draft → archived is not a transition
    when = clock.now() + timedelta(minutes=2)
    await articles.transition(eddie, draft.id, "schedule", publish_at=when)
    async with ct.database.session() as session:
        job = (
            await session.execute(text("SELECT payload FROM core.job WHERE kind = :k"), {"k": PUBLISH_JOB})
        ).scalar_one()
    assert await articles.run_scheduled(job) is False  # too early
    clock.advance(timedelta(minutes=3))
    assert await articles.run_scheduled(job) is True
    assert await articles.run_scheduled(job) is False  # duplicate run: nothing happens
    assert await articles.sweep() == 0
    async with ct.database.session() as session:
        published = (await session.execute(text("SELECT status, publish_seq FROM news.articles"))).one()
        events = (
            await session.execute(
                text("SELECT count(*) FROM events.events WHERE type = 'news.article_published'")
            )
        ).scalar_one()
    assert tuple(published) == ("published", 1) and events == 1
    assert [type(r.audience) for r in ct.outbox.sent] == [AllAuthenticated] and ct.outbox.sent[
        0
    ].category == "news.published"
    listing = (await client.get("/api/v1/news")).json()["items"]
    assert [i["title"] for i in listing] == ["Release 2.0"]
    # featuring: window + cap (3) + order by priority
    boss = ct.p("boss")
    for n in range(4):
        extra = await articles.create(boss, ArticleInput(f"Extra {n}", "x"))
        await articles.transition(boss, extra.id, "publish")
        await articles.feature(boss, extra.id, None, None, n)
    await articles.feature(boss, draft.id, clock.now() + timedelta(days=1), None, 99)  # not yet
    featured = (await client.get("/api/v1/news/featured")).json()
    assert [f["title"] for f in featured] == ["Extra 3", "Extra 2", "Extra 1"]
    # archive: out of discovery, readable by direct link
    await articles.transition(eddie, draft.id, "archive")
    assert "Release 2.0" not in [i["title"] for i in (await client.get("/api/v1/news")).json()["items"]]
    archived = (await client.get(f"/api/v1/news/{draft.slug}")).json()
    assert archived["archived"] is True
    await articles.transition(eddie, draft.id, "restore")
    assert (await articles.get(draft.slug, ct.p("rita"))).status == "published"
    # deleting: a published article must be archived first; archived deletion asks for a confirmation
    await login(client, "boss")
    assert (await client.post(f"/api/v1/admin/news/articles/{draft.id}/delete", json={})).status_code == 409
    await client.post(f"/api/v1/admin/news/articles/{draft.id}/lifecycle/archive")
    asked = await client.post(f"/api/v1/admin/news/articles/{draft.id}/delete", json={})
    assert asked.status_code == 409 and asked.json()["code"] == "authz.confirmation_required"
    token = asked.json()["confirmation"]
    assert (
        await client.post(f"/api/v1/admin/news/articles/{draft.id}/delete", json={"confirmation": token})
    ).status_code == 204
    await login(client, "rita")
    assert (await client.get(f"/api/v1/news/{draft.slug}")).status_code == 404


async def test_audience_and_actions(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID]
) -> None:
    articles = ct.news.articles
    boss = ct.p("boss")
    staff = await articles.create(
        boss,
        ArticleInput(
            "Support rota",
            "secret plans",
            audience={"mode": "roles", "refs": ["support"]},
            notify_on_publish=True,
        ),
    )
    await articles.transition(boss, staff.id, "publish")
    await articles.feature(boss, staff.id, None, None, 1)
    assert [type(r.audience) for r in ct.outbox.sent] == [Role]
    for name, visible in (("rita", False), ("sam", True)):
        viewer = ct.p(name)
        assert (staff.id in [a.id for a in (await articles.listing(viewer))[0]]) is visible
        assert (staff.id in [a.id for a in await articles.featured(viewer)]) is visible
        provider = ct.search.provider("news")
        assert provider is not None
        hits = await provider.search(query("rota"), viewer, LocaleContext(), limit=10, cursor=None)
        assert bool(hits.items) is visible
    await login(client, "rita")
    assert (await client.get(f"/api/v1/news/{staff.slug}")).status_code == 404
    # automation action: runs under the author's authority
    action = ct.actions.get("content.publish")
    assert action is not None and action.permission == "news.publish"
    second = await articles.create(boss, ArticleInput("Auto", "x"))
    result = await action.run({"article": str(second.id)}, automation(people["eddie"]))
    assert result["publish_seq"] == 1
    third = await articles.create(boss, ArticleInput("Not allowed", "x"))
    with pytest.raises(Exception):  # noqa: B017 — a reader's automation cannot publish
        await action.run({"article": str(third.id)}, automation(people["rita"]))
