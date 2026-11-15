"""Issue 457 — Portalab's member guide in the wiki: installed in English with its French translation, read
in each member's language, kept up to date by each release, never over what an administrator changed or
deleted, removed when switched off and back when switched on, imported pages adopted, the site's currency
written in, its screenshots served read-only; nothing while the wiki module is off."""

import io
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from PIL import Image
from sqlalchemy import select

from portalab.capabilities.i18n import SITE_TERMS, SiteTerms
from portalab.capabilities.plugins import TOGGLE_WRITER
from portalab.core.time import FixedClock
from portalab.modules.wiki.guide import GUIDE_NOTE, GuideSync, read_guide, shot_path
from portalab.modules.wiki.models import GuidePage, Page, PageTranslation
from tests.integration.content.conftest import ContentHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration

TOP = "---\nslug: guide-membre\ntitle: {title}\nposition: 0\nparent: none\ntags: [guide]\n---\n{body}\n"
PAGE = (
    "---\nslug: guide-foyer\ntitle: {title}\nposition: 3\nhelp_keys: [household.page]\ntags: [{tag}]\n---\n"
    "{body}\n\n![{alt}](shot:foyer-qui)\n"
)


def write_guide(
    root: Path, *, en_body: str = "Earn Coins with your household.", fr_body: str = "Gagnez des Coins."
) -> None:
    for language, (top, title, tag, body, alt) in {
        "en": ("Portalab member guide", "My household", "household", en_body, "Who is there"),
        "fr": ("Guide du membre Portalab", "Mon foyer", "foyer", fr_body, "Qui est là"),
    }.items():
        folder = root / language
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "guide-membre.md").write_text(TOP.format(title=top, body="The guide."), encoding="utf-8")
        (folder / "guide-foyer.md").write_text(
            PAGE.format(title=title, tag=tag, body=body, alt=alt), encoding="utf-8"
        )
    shots = root / "images" / "fr"
    shots.mkdir(parents=True, exist_ok=True)
    picture = io.BytesIO()
    Image.new("RGB", (4, 4), "orange").save(picture, "JPEG")
    (shots / "foyer-qui.jpg").write_bytes(picture.getvalue())


class Toggles:
    def __init__(self, wiki: bool) -> None:
        self.wiki = wiki

    async def is_enabled(self, kind: str, ref: str, *, default: bool = True) -> bool:
        return self.wiki if (kind, ref) == ("module", "wiki") else default

    async def set(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover — not used here
        return None


class Terms:
    version = 1

    def terms(self, language: str) -> SiteTerms:
        return (
            SiteTerms(currency_one="Coin", currency_other="Coins")
            if language == "en"
            else SiteTerms()
        )

    async def refresh(self) -> None:
        return None


async def page_of(ct: ContentHarness, slug: str) -> Page:
    async with ct.database.session() as session:
        found = await session.scalar(select(Page).where(Page.slug == slug))
    assert found is not None
    return found


async def test_installs_reads_in_each_language_and_keeps_up(
    client: httpx.AsyncClient,
    ct: ContentHarness,
    people: dict[str, UUID],
    tmp_path: Path,
    clock: FixedClock,
) -> None:
    root = tmp_path / "guide"
    write_guide(root)
    ct.ev.full.identity.capabilities.provide(SITE_TERMS, Terms(), instance_ref="test-terms", owner="test")
    sync = ct.wiki.guide = GuideSync(ct.wiki.pages, ct.ev.full.identity.capabilities, root, clock=clock)
    first = await sync.run()
    assert first.created == ["guide-membre", "guide-foyer"]
    page = await page_of(ct, "guide-foyer")
    top = await page_of(ct, "guide-membre")
    assert page.language == "en" and page.status == "published" and page.parent_id == top.id
    assert page.position == 3 and page.help_keys == ["household.page"] and page.readable_by_ai

    await login(client, "rita")  # a reader
    english = (await client.get("/api/v1/wiki/pages/guide-foyer")).json()
    assert english["title"] == "My household" and "Earn Coins with your household." in english["html"]
    # the English text has no screenshot of its own: the French one is shown
    assert '<img src="/api/v1/wiki/guide/shots/fr/foyer-qui.jpg" alt="Who is there">' in english["html"]
    french = (await client.get("/api/v1/wiki/pages/guide-foyer", params={"lang": "fr"})).json()
    assert (
        french["title"] == "Mon foyer" and french["is_translation"] and "Gagnez des Coins." in french["html"]
    )
    assert sorted(english["tags"]) == ["foyer", "household"]
    tree = (await client.get("/api/v1/wiki/tree", params={"lang": "fr"})).json()
    assert tree[0]["title"] == "Guide du membre Portalab" and tree[0]["children"][0]["title"] == "Mon foyer"
    shot = await client.get("/api/v1/wiki/guide/shots/fr/foyer-qui.jpg")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/jpeg"
    assert (await client.get("/api/v1/wiki/guide/shots/fr/..%2F..%2Fen%2Fguide-foyer.jpg")).status_code == 404
    assert (await client.get("/api/v1/wiki/guide/shots/en/foyer-qui.jpg")).status_code == 404
    assert shot_path(root, "fr", "../fr/foyer-qui") is None and shot_path(root, "../fr", "foyer-qui") is None

    again = await sync.run()  # nothing changed in the release
    assert not again.changed and (await page_of(ct, "guide-foyer")).current_version == 1

    write_guide(root, en_body="Earn Coins together.", fr_body="Gagnez ensemble.")  # the next release
    updated = await sync.run()
    assert updated.updated == ["guide-foyer"]
    page = await page_of(ct, "guide-foyer")
    assert page.current_version == 2
    async with ct.database.session() as session:
        translation = await session.get(PageTranslation, (page.id, "fr"))
    assert translation is not None and translation.body_md.startswith("Gagnez ensemble.")
    assert translation.source_version == 2


async def test_the_administrator_s_word_wins(
    client: httpx.AsyncClient,
    ct: ContentHarness,
    people: dict[str, UUID],
    tmp_path: Path,
    clock: FixedClock,
) -> None:
    root = tmp_path / "guide"
    write_guide(root)
    sync = GuideSync(ct.wiki.pages, ct.ev.full.identity.capabilities, root, clock=clock)
    await sync.run()
    page = await page_of(ct, "guide-foyer")
    await login(client, "eddie")  # an editor changes the page
    edited = await client.put(
        f"/api/v1/wiki/pages/{page.id}",
        json={
            "title": "Our household",
            "body_md": "House rules.",
            "base_version": 1,
            "audience": {"mode": "all"},
        },
    )
    assert edited.status_code == 200, edited.text
    write_guide(root, en_body="A new release text.")
    report = await sync.run()
    assert report.kept == ["guide-foyer"] and not report.updated
    assert (await page_of(ct, "guide-foyer")).title == "Our household"


async def test_deleted_by_the_administrator_then_switched_off_and_on(
    ct: ContentHarness,
    people: dict[str, UUID],
    tmp_path: Path,
    clock: FixedClock,
) -> None:
    root = tmp_path / "guide"
    write_guide(root)
    sync = GuideSync(ct.wiki.pages, ct.ev.full.identity.capabilities, root, clock=clock)
    await sync.run()
    page = await page_of(ct, "guide-foyer")
    await ct.wiki.pages.set_status(ct.p("boss"), page.id, "deleted")
    await sync.run()
    async with ct.database.session() as session:
        assert (await session.get(GuidePage, "guide-foyer")).state == "dismissed"  # type: ignore[union-attr]
    assert (await page_of(ct, "guide-foyer")).status == "deleted"
    await sync.run()
    assert (await page_of(ct, "guide-foyer")).status == "deleted"  # still not brought back

    off = await sync.run(enabled=False)  # the guide switched off: what it owns goes
    assert off.removed == ["guide-membre"]
    assert (await page_of(ct, "guide-membre")).status == "deleted"
    on = await sync.run(enabled=True)  # and on again: every page back
    assert set(on.adopted) == {"guide-membre", "guide-foyer"}
    assert (await page_of(ct, "guide-foyer")).status == "published"
    assert (await page_of(ct, "guide-membre")).status == "published"


async def test_adopts_a_page_imported_by_hand_and_leaves_others_alone(
    ct: ContentHarness,
    people: dict[str, UUID],
    tmp_path: Path,
    clock: FixedClock,
) -> None:
    from portalab.modules.wiki.pages import PageInput

    boss = ct.p("boss")
    imported = await ct.wiki.pages.create(
        boss,
        PageInput(title="Mon foyer", body_md="Ancien texte.", slug="guide-foyer", language="fr",
                  change_note="Guide du membre", audience={"mode": "all"}),
        publish=True,
    )  # fmt: skip
    mine = await ct.wiki.pages.create(
        boss,
        PageInput(title="Ours", body_md="Ours.", slug="guide-membre", audience={"mode": "all"}),
        publish=True,
    )
    root = tmp_path / "guide"
    write_guide(root)
    report = await GuideSync(ct.wiki.pages, ct.ev.full.identity.capabilities, root, clock=clock).run()
    assert report.adopted == ["guide-foyer"] and not report.created
    adopted = await page_of(ct, "guide-foyer")
    assert adopted.id == imported.id and adopted.language == "en" and adopted.title == "My household"
    other = await page_of(ct, "guide-membre")
    assert other.id == mine.id and other.title == "Ours"  # an administrator's own page: never touched
    async with ct.database.session() as session:
        notes = await ct.wiki.pages.revisions(adopted.id, boss)
        assert notes[0].change_note == GUIDE_NOTE
        assert await session.get(GuidePage, "guide-membre") is None


async def test_nothing_while_the_wiki_module_is_off(
    ct: ContentHarness, tmp_path: Path, clock: FixedClock
) -> None:
    root = tmp_path / "guide"
    write_guide(root)
    real = ct.ev.full.identity.capabilities

    class Capabilities:  # the module manager says the wiki is off
        def system_providers(self, name: str) -> list[Any]:
            if name == TOGGLE_WRITER:
                return [type("P", (), {"provider": Toggles(wiki=False)})()]
            return real.system_providers(name)

    caps = Capabilities()
    report = await GuideSync(ct.wiki.pages, caps, root, clock=clock).run()
    assert report.skipped == "the wiki module is off" and not report.changed
    async with ct.database.session() as session:
        assert (await session.scalar(select(Page).where(Page.slug == "guide-foyer"))) is None


def test_the_shipped_guide_reads_whole() -> None:
    """The guide of this release: every page has its English source, and its French translation."""
    from portalab.modules.wiki.guide import guide_root

    root = guide_root()
    assert root is not None
    docs = read_guide(root)
    assert len(docs) >= 20
    assert all({"en", "fr"} <= set(doc.texts) for doc in docs), [d.slug for d in docs if len(d.texts) < 2]
    assert sum(1 for doc in docs if doc.parent is None) == 1  # one top page: the guide's
