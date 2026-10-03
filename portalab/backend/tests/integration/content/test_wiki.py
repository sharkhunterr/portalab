"""011 T006/T010/T013/T015 — wiki pages: create/read/update with ``base_version`` and a 409 diff on a stale
base; reader/editor/admin matrix; unsafe content inert; oversize rejected; append-only revisions, compare
with textual markers, restore = new revision; history needs ``wiki.history.read``; tree/move/breadcrumbs;
knowledge and help bounded by the asking principal; assets sniffed/re-encoded and readable only with the
owner's read permission; per-viewer link states without title leaks."""

import io
from uuid import UUID

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


def page(title: str, body: str, **extra: object) -> dict[str, object]:
    return {"title": title, "body_md": body, **extra}


async def test_pages_conflicts_history(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID]
) -> None:
    await login(client, "rita")
    assert (await client.post("/api/v1/wiki/pages", json=page("Nope", "x"))).status_code == 403
    await login(client, "eddie")
    created = await client.post(
        "/api/v1/wiki/pages",
        json=page(
            "Getting started",
            "# Hello\n<script>alert(1)</script>\n[ext](https://example.org)",
            tags=["Guide"],
        ),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    page_id, slug = body["id"], body["slug"]
    assert slug == "getting-started" and body["status"] == "draft" and "<script>" not in body["html"]
    assert 'data-external="true"' in body["html"] and body["tags"] == ["guide"]
    await login(client, "rita")
    assert (await client.get(f"/api/v1/wiki/pages/{slug}")).status_code == 404  # drafts: editors only
    await login(client, "eddie")  # editors hold wiki.publish (003 catalog)
    assert (await client.post(f"/api/v1/wiki/pages/{page_id}/publish")).json()["status"] == "published"
    await login(client, "rita")
    read = (await client.get(f"/api/v1/wiki/pages/{slug}")).json()
    assert read["title"] == "Getting started" and read["can_edit"] is False
    # optimistic concurrency: two editors from version 1
    await login(client, "eddie")
    first = await client.put(
        f"/api/v1/wiki/pages/{page_id}", json=page("Getting started", "# Hello\nv2", base_version=1)
    )
    assert first.status_code == 200 and first.json()["version"] == 2
    stale = await client.put(
        f"/api/v1/wiki/pages/{page_id}", json=page("Getting started", "# Hello\nother", base_version=1)
    )
    assert stale.status_code == 409 and stale.json()["code"] == "wiki.version_conflict"
    assert {"op": "insert", "text": "v2"} in stale.json()["diff"]["lines"]
    third = await client.put(
        f"/api/v1/wiki/pages/{page_id}", json=page("Getting started", "# Hello\nv3", base_version=2)
    )
    assert third.json()["version"] == 3
    too_big = await client.put(f"/api/v1/wiki/pages/{page_id}", json=page("x", "a" * 200_001, base_version=3))
    assert too_big.status_code == 422 and too_big.json()["code"] == "content.unsafe_markdown"
    # history: editors (wiki.history.read) yes, readers no
    revisions = (await client.get(f"/api/v1/wiki/pages/{page_id}/revisions")).json()
    assert [r["version"] for r in revisions] == [3, 2, 1]
    diff = (await client.get(f"/api/v1/wiki/pages/{page_id}/compare", params={"from": 2, "to": 3})).json()
    assert {"op": "delete", "text": "v2"} in diff["lines"] and {"op": "insert", "text": "v3"} in diff["lines"]
    restored_r = await client.post(f"/api/v1/wiki/pages/{page_id}/restore", json={"version": 1})
    assert restored_r.status_code == 200, restored_r.text
    restored = restored_r.json()
    assert restored["version"] == 4 and "<script>" not in restored["html"]
    detail = (await client.get(f"/api/v1/wiki/pages/{page_id}/revisions/4")).json()
    assert detail["restored_from_version"] == 1
    async with ct.database.session() as session:
        assert (await session.execute(text("SELECT count(*) FROM wiki.revisions"))).scalar_one() == 4
    with pytest.raises(Exception):  # noqa: B017 — append-only revisions
        async with ct.database.unit_of_work() as uow:
            await uow.session.execute(text("UPDATE wiki.revisions SET body_md = 'x'"))
    await login(client, "rita")
    assert (await client.get(f"/api/v1/wiki/pages/{page_id}/revisions")).status_code == 403


async def test_tree_knowledge_help(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID]
) -> None:
    boss, ed = ct.p("boss"), ct.p("eddie")
    from portalab.modules.wiki.pages import PageInput

    root = await ct.wiki.pages.create(boss, PageInput("Services", "All about services"), publish=True)
    child = await ct.wiki.pages.create(
        boss,
        PageInput(
            "Restart Plex",
            "How to restart the media server",
            parent_id=root.id,
            readable_by_ai=True,
            help_keys=["services.detail"],
        ),
        publish=True,
    )
    secret = await ct.wiki.pages.create(
        boss,
        PageInput(
            "Admin runbook",
            "restart the media server as root",
            audience={"mode": "roles", "refs": ["admin"]},
            readable_by_ai=True,
        ),
        publish=True,
    )
    tree = await ct.wiki.pages.tree(ct.p("rita"))
    assert [n["title"] for n in tree] == ["Services"] and [c["title"] for c in tree[0]["children"]] == [
        "Restart Plex"
    ]
    assert await ct.wiki.pages.breadcrumbs(child.id, ct.p("rita")) == [
        {"id": str(root.id), "slug": root.slug, "title": "Services"}
    ]
    with pytest.raises(Exception):  # noqa: B017 — a page cannot move under its own child
        await ct.wiki.pages.move(ed, root.id, child.id, 0)
    rita_hits = await ct.wiki.knowledge.search("media server", ct.p("rita"), for_ai=True)
    boss_hits = await ct.wiki.knowledge.search("media server", boss, for_ai=True)
    assert [h.title for h in rita_hits] == ["Restart Plex"]
    assert {h.title for h in boss_hits} == {"Restart Plex", "Admin runbook"}
    assert [h.title for h in await ct.wiki.knowledge.search("media server", ct.p("rita"))] == ["Restart Plex"]
    await login(client, "rita")
    help_hits = (await client.get("/api/v1/help", params={"key": "services.detail"})).json()
    assert [h["title"] for h in help_hits] == ["Restart Plex"]
    del secret


async def test_assets_and_links(
    client: httpx.AsyncClient, ct: ContentHarness, people: dict[str, UUID]
) -> None:
    from portalab.modules.wiki.pages import PageInput

    boss = ct.p("boss")
    public = await ct.wiki.pages.create(boss, PageInput("Public", "x"), publish=True)
    private = await ct.wiki.pages.create(
        boss, PageInput("Private", "y", audience={"mode": "roles", "refs": ["admin"]}), publish=True
    )
    archived = await ct.wiki.pages.create(boss, PageInput("Old", "z"), publish=True)
    await ct.wiki.pages.set_status(boss, archived.id, "archived")
    gone = await ct.wiki.pages.create(boss, PageInput("Gone", "z"), publish=True)
    await ct.wiki.pages.set_status(boss, gone.id, "deleted")
    image = io.BytesIO()
    Image.new("RGB", (20, 20), (0, 128, 0)).save(image, format="PNG")
    await login(client, "eddie")
    upload = await client.post(
        "/api/v1/content/assets",
        params={"owner_ref": f"portalab://wiki/{private.id}", "filename": "chart.png"},
        content=image.getvalue(),
        headers={"Content-Type": "image/png"},
    )
    assert upload.status_code == 201
    private_asset = upload.json()["id"]
    upload = await client.post(
        "/api/v1/content/assets",
        params={"owner_ref": f"portalab://wiki/{public.id}", "filename": "chart.png"},
        content=image.getvalue(),
        headers={"Content-Type": "image/png"},
    )
    assert upload.status_code == 201 and upload.json()["markdown"].startswith("![chart.jpg](portalab-asset:")
    asset = upload.json()["id"]
    disguised = await client.post(
        "/api/v1/content/assets",
        params={"owner_ref": f"portalab://wiki/{public.id}", "filename": "cute.png"},
        content=b"MZ\x90\x00" + b"\x00" * 100,
        headers={"Content-Type": "image/png"},
    )
    assert disguised.status_code == 422 and disguised.json()["code"] == "content.unsafe_upload"
    await login(client, "rita")
    served = await client.get(f"/api/v1/content/assets/{asset}")
    assert served.status_code == 200 and served.headers["x-content-type-options"] == "nosniff"
    assert (
        await client.get(f"/api/v1/content/assets/{private_asset}")
    ).status_code == 404  # owner unreadable
    refs = [f"portalab://wiki/{x}" for x in (public.id, private.id, archived.id, gone.id)] + [
        "portalab://wiki/nope",
        "not a ref",
    ]
    states = (await client.post("/api/v1/content/links/resolve", json={"refs": refs})).json()
    assert [(s["state"], s["title"]) for s in states] == [
        ("ok", "Public"),
        ("forbidden", None),  # no title leak
        ("archived", "Old"),
        ("deleted", None),
        ("unavailable", None),
        ("unavailable", None),
    ]
    preview = (
        await client.post("/api/v1/content/render", json={"markdown": "**b** <script>x</script>"})
    ).json()
    assert preview["html"].startswith("<p><strong>b</strong> &lt;script&gt;")
