"""#299 — the news sources: an editor previews a feed (a web page announcing it will do), adds it — read at
once, its items kept with their picture copied and the library titles they name, without what its excluded
words match —; readers see them, a title's news among them; an item hidden goes, a source not changed is not
read again; a private address is refused unless the local network is allowed; a source removed takes its
items and pictures along."""

import io
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from sqlalchemy import select

from portalab.capabilities.media import MENTIONS, Mention
from portalab.core.blobstore import FileSystemBlobStore
from portalab.modules.news.models import Feed
from portalab.modules.news.participant import NewsParticipant
from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login
from tests.integration.privacy.conftest import NOW

FEED = """<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>Écrans</title>
<link>https://news.example.org/</link>
<item><title>Dune Part Two arrive en 4K</title><link>https://news.example.org/dune</link><guid>1</guid>
<description>Le film de Denis Villeneuve.</description><pubDate>Fri, 30 Oct 2026 09:00:00 +0000</pubDate>
<media:thumbnail url="https://cdn.example.org/dune.png"/></item>
<item><title>Rumeur sur une suite</title><link>https://news.example.org/rumeur</link><guid>2</guid>
<description>Rien de sûr.</description><pubDate>Thu, 29 Oct 2026 09:00:00 +0000</pubDate></item>
<item><title>Le box-office du week-end</title><link>https://news.example.org/bo</link><guid>3</guid>
<pubDate>Wed, 28 Oct 2026 09:00:00 +0000</pubDate></item>
</channel></rss>""".encode()
PAGE = b'<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>'


def _png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 60), (200, 120, 40)).save(out, "PNG")
    return out.getvalue()


class Site:
    def __init__(self) -> None:
        self.reads = 0
        self.picture = _png()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://news.example.org/":
            return httpx.Response(200, content=PAGE, headers={"content-type": "text/html"})
        if url == "https://news.example.org/feed.xml":
            if request.headers.get("if-none-match") == '"v1"':
                return httpx.Response(304)
            self.reads += 1
            headers = {"content-type": "application/rss+xml", "etag": '"v1"'}
            return httpx.Response(200, content=FEED, headers=headers)
        if url == "https://cdn.example.org/dune.png":
            return httpx.Response(200, content=self.picture, headers={"content-type": "image/png"})
        return httpx.Response(404)


class Library:
    """What the media module would say: « Dune Part Two » is a library title, Denis Villeneuve a person."""

    async def mentions(self, texts: Sequence[str], limit: int = 6) -> list[list[Mention]]:
        out = []
        for text in texts:
            found = []
            if "Dune Part Two" in text:
                found.append(Mention("title", "obj-dune", "Dune Part Two", "/media/obj-dune"))
            if "Denis Villeneuve" in text:
                found.append(Mention("person", "Denis Villeneuve", "Denis Villeneuve", "/media/people/x"))
            out.append(found)
        return out


async def _addresses(host: str) -> list[str]:
    return ["192.168.1.20"] if host == "nas.lan" else ["93.184.216.34"]


async def test_sources_bring_news_from_elsewhere(
    ct: ContentHarness, client: httpx.AsyncClient, people: dict[str, Any], tmp_path: Path
) -> None:
    site = Site()
    sources = ct.news.sources
    sources.transport = httpx.MockTransport(site)
    sources.resolver = _addresses
    sources.blobs = FileSystemBlobStore(tmp_path / "news-blobs")
    ct.ev.full.identity.capabilities.provide(MENTIONS, Library(), instance_ref="test-media", owner="test")

    await login(client, "boss")
    shown = await client.post("/api/v1/admin/news/sources/preview", json={"url": "https://news.example.org/"})
    assert shown.status_code == 200, shown.text
    preview = shown.json()
    assert preview["url"] == "https://news.example.org/feed.xml" and preview["title"] == "Écrans"
    assert [m["label"] for m in preview["items"][0]["mentions"]] == ["Dune Part Two", "Denis Villeneuve"]

    body = {"name": "Écrans", "url": "https://news.example.org/feed.xml", "exclude_words": ["rumeur"]}
    saved = (await client.put("/api/v1/admin/news/sources", json=body)).json()
    assert saved["status"] == "ok" and saved["items"] == 2  # read at once, the rumour left out
    again = await client.put("/api/v1/admin/news/sources", json=body)
    assert again.status_code == 422  # the same source twice

    await login(client, "rita")
    items = (await client.get("/api/v1/news/sources/items")).json()["items"]
    assert [i["title"] for i in items] == ["Dune Part Two arrive en 4K", "Le box-office du week-end"]
    dune = items[0]
    assert dune["source"] == "Écrans" and dune["picture"] and items[1]["picture"] is None
    picture = await client.get(dune["picture"])
    assert picture.status_code == 200 and picture.headers["content-type"].startswith("image/")
    assert "news.example.org" not in picture.text  # the portal's copy, not the site's address
    about = (await client.get("/api/v1/news/sources/items", params={"title": "obj-dune"})).json()["items"]
    assert [i["id"] for i in about] == [dune["id"]]
    by_person = await client.get("/api/v1/news/sources/items", params={"person": "Denis Villeneuve"})
    assert len(by_person.json()["items"]) == 1
    assert (await client.get("/api/v1/admin/news/sources")).status_code == 403  # the editors' only

    await login(client, "boss")
    hidden = await client.put(f"/api/v1/admin/news/sources/items/{items[1]['id']}", json={"hidden": True})
    assert hidden.status_code == 204
    assert len((await client.get("/api/v1/news/sources/items")).json()["items"]) == 1
    assert len((await client.get("/api/v1/admin/news/sources/items")).json()["items"]) == 2

    refreshed = (await client.post(f"/api/v1/admin/news/sources/{saved['id']}/refresh")).json()
    assert refreshed == {"added": 0, "status": "ok", "last_error": None}
    assert site.reads == 2  # the preview, the first reading — then « not changed »

    private = await client.post("/api/v1/admin/news/sources/preview", json={"url": "https://nas.lan/rss"})
    assert private.status_code == 422 and "private" in private.json()["detail"]

    assert (await client.delete(f"/api/v1/admin/news/sources/{saved['id']}")).status_code == 204
    assert (await client.get("/api/v1/news/sources/items")).json()["items"] == []
    assert not [p for p in (tmp_path / "news-blobs").rglob("*") if p.is_file()]  # its pictures too


OPML = """<?xml version="1.0"?><opml version="2.0"><head><title>x</title></head><body>
<outline text="Ciné"><outline type="rss" text="Écrans" xmlUrl="https://news.example.org/feed.xml"/>
<outline type="rss" text="Autre" xmlUrl="https://other.example.org/rss"/></outline>
<outline text="no feed"/><outline xmlUrl="javascript:alert(1)"/></body></opml>"""


async def test_members_follow_sources_of_their_own(
    ct: ContentHarness, client: httpx.AsyncClient, people: dict[str, Any], tmp_path: Path
) -> None:
    site = Site()
    sources = ct.news.sources
    sources.transport = httpx.MockTransport(site)
    sources.resolver = _addresses
    sources.blobs = FileSystemBlobStore(tmp_path / "news-blobs")
    ct.ev.full.identity.capabilities.provide(MENTIONS, Library(), instance_ref="test-media", owner="test")

    await login(client, "rita")
    mine = await client.post("/api/v1/me/news/sources", json={"url": "https://news.example.org/"})
    assert mine.status_code == 200, mine.text
    source = mine.json()
    assert source["name"] == "Écrans" and source["items"] == 3  # the page's feed, read at once
    own = (await client.get("/api/v1/me/news/sources/items")).json()["items"]
    assert len(own) == 3 and (await client.get(own[0]["picture"])).status_code == 200
    # mine alone: not on « À la une », not in the editors' list, not another member's
    assert (await client.get("/api/v1/news/sources/items")).json()["items"] == []
    # but « in the news » for a title I follow reads my sources too
    about = (await client.get("/api/v1/news/sources/items", params={"title": "obj-dune"})).json()["items"]
    assert [i["title"] for i in about] == ["Dune Part Two arrive en 4K"]
    # what they published since I last read « Mon fil »: its badge
    assert await sources.published_since(people["rita"], NOW - timedelta(days=1)) == 3
    assert await sources.published_since(people["rita"], NOW) == 0  # read since
    assert await sources.published_since(people["sam"], NOW - timedelta(days=1)) == 0
    exported = await client.get("/api/v1/me/news/sources/opml")
    assert "https://news.example.org/feed.xml" in exported.text and "opml" in exported.headers["content-type"]

    await login(client, "sam")
    assert (await client.get("/api/v1/me/news/sources/items")).json()["items"] == []
    assert (await client.get("/api/v1/news/sources/items", params={"title": "obj-dune"})).json()[
        "items"
    ] == []
    assert (await client.get(own[0]["picture"])).status_code == 404  # nor its pictures
    imported = (await client.post("/api/v1/me/news/sources/opml", json={"opml": OPML})).json()
    assert imported == {"added": 2, "skipped": 0}  # the same address as rita's: read once for both
    assert {s["name"] for s in (await client.get("/api/v1/me/news/sources")).json()["items"]} == {
        "Écrans",
        "Autre",
    }

    await login(client, "boss")
    assert (await client.get("/api/v1/admin/news/sources")).json()["items"] == []
    # the editors add the same address: it becomes theirs too (members keep it)
    body = {"name": "Écrans (rédaction)", "url": source["url"]}
    promoted = (await client.put("/api/v1/admin/news/sources", json=body)).json()
    assert promoted["id"] == source["id"]
    assert len((await client.get("/api/v1/news/sources/items")).json()["items"]) == 3
    # taken off « À la une »: the members who follow it keep it
    assert (await client.delete(f"/api/v1/admin/news/sources/{source['id']}")).status_code == 204
    assert (await client.get("/api/v1/news/sources/items")).json()["items"] == []
    await login(client, "rita")
    assert len((await client.get("/api/v1/me/news/sources/items")).json()["items"]) == 3

    # rita stops following: sam still does; sam goes: the source nobody follows goes too
    assert (await client.delete(f"/api/v1/me/news/sources/{source['id']}")).status_code == 204
    assert (await client.get("/api/v1/me/news/sources")).json()["items"] == []
    await NewsParticipant(ct.database).erase(people["sam"], "final")
    await sources.run_due()
    async with ct.database.session() as session:
        assert (await session.execute(select(Feed))).first() is None
