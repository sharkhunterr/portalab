"""Issue 411 — the portal's own pictures are carried in the e-mail: those it serves (relative, or on the
portal's address) by ``cid:``, read once each, real image formats only, bounded; any other picture stays a
link, and one that cannot be read stays a link too."""

from uuid import UUID, uuid4

import pytest

from portalab.modules.notifications.channels import inline
from portalab.modules.notifications.channels.inline import embed, kind_of

JPEG = b"\xff\xd8\xff\xe0" + b"j" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 100
PORTAL = "https://portal.example"


class Pictures:
    prefix = "/api/v1/newsletters/pictures/"

    def __init__(self, data: dict[str, bytes | None] | None = None, fail: bool = False) -> None:
        self.data = data or {}
        self.asked: list[tuple[str, UUID | None]] = []
        self.fail = fail

    async def image(self, path: str, reader: UUID | None) -> bytes | None:
        self.asked.append((path, reader))
        if self.fail:
            raise RuntimeError("store down")
        return self.data.get(path)


def test_kinds() -> None:
    assert kind_of(JPEG) == "image/jpeg" and kind_of(PNG) == "image/png"
    assert kind_of(b"GIF89a....") == "image/gif"
    assert kind_of(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert kind_of(b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>") is None
    assert kind_of(b"<html>") is None


async def test_the_portals_pictures_are_embedded() -> None:
    reader = uuid4()
    source = Pictures({"tok/a": JPEG, "tok/b": PNG})
    body = (
        f'<img src="{PORTAL}/api/v1/newsletters/pictures/tok/a" alt="A">'
        '<img src="/api/v1/newsletters/pictures/tok/b" alt="B">'
        f'<img src="{PORTAL}/api/v1/newsletters/pictures/tok/a" alt="A again">'
        '<img src="https://image.tmdb.org/t/p/w342/x.jpg" alt="elsewhere">'
        '<img src="https://other.example/api/v1/newsletters/pictures/tok/a" alt="another host">'
    )
    html, images = await embed(body, PORTAL, [source], reader)
    assert [i.mime for i in images] == ["image/jpeg", "image/png"]
    assert html.count(f'src="cid:{images[0].cid}"') == 2  # one part for a picture shown twice
    assert f'src="cid:{images[1].cid}"' in html
    assert 'src="https://image.tmdb.org/t/p/w342/x.jpg"' in html  # not the portal's: still a link
    assert 'src="https://other.example/api/v1/newsletters/pictures/tok/a"' in html
    assert source.asked == [("tok/a", reader), ("tok/b", reader)]
    assert all(i.cid.endswith("@portalab") and " " not in i.cid for i in images)


async def test_what_is_not_embedded_stays_a_link() -> None:
    svg = b"<svg><script>alert(1)</script></svg>"
    source = Pictures({"t/missing": None, "t/svg": svg, "t/big": b"\xff\xd8\xff" + b"0" * (3 * 1024 * 1024)})
    body = "".join(f'<img src="/api/v1/newsletters/pictures/t/{n}">' for n in ("missing", "svg", "big"))
    html, images = await embed(body, PORTAL, [source], None)
    assert images == () and html == body
    html, images = await embed(body, PORTAL, [Pictures(fail=True)], None)
    assert images == () and html == body  # a store that fails never stops the e-mail
    assert await embed("<p>No picture</p>", PORTAL, [source], None) == ("<p>No picture</p>", ())
    assert await embed(body, PORTAL, [], None) == (body, ())


async def test_escaped_addresses_and_ports() -> None:
    source = Pictures({"tok/a?x=1&y=2": JPEG})
    body = '<img src="https://portal.example:8443/api/v1/newsletters/pictures/tok/a?x=1&amp;y=2">'
    _, images = await embed(body, "https://portal.example:8443", [source], None)
    assert len(images) == 0  # the query is not part of the path: « tok/a » was asked
    source.data["tok/a"] = JPEG
    html, images = await embed(body, "https://portal.example:8443", [source], None)
    assert len(images) == 1 and "cid:" in html
    _, images = await embed(body, "https://portal.example", [source], None)  # another port: not the portal
    assert images == ()


async def test_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inline, "MAX_IMAGES", 2)
    monkeypatch.setattr(inline, "MAX_TOTAL_BYTES", len(JPEG) * 3)
    source = Pictures({f"t/{n}": JPEG for n in range(5)})
    body = "".join(f'<img src="/api/v1/newsletters/pictures/t/{n}">' for n in range(5))
    html, images = await embed(body, PORTAL, [source], None)
    assert len(images) == 2 and html.count("cid:") == 2
    monkeypatch.setattr(inline, "MAX_IMAGES", 10)
    _, images = await embed(body, PORTAL, [source], None)
    assert len(images) == 3  # the total size stops it


async def test_an_editions_pictures() -> None:
    from portalab.modules.news.editions.pictures import EditionPictures

    class Editions:
        def __init__(self) -> None:
            self.asked: list[tuple[str, str]] = []

        async def picture(self, token: str, image_id: str) -> bytes | None:
            self.asked.append((token, image_id))
            return JPEG

    editions = Editions()
    source = EditionPictures(editions)  # type: ignore[arg-type]
    token = "t" * 43
    poster = "0E0F6A2B-0000-4000-8000-000000000001"
    assert await source.image(f"{token}/{poster}", None) == JPEG
    assert await source.image(f"{token}/t-tmdb.12", None) == JPEG
    assert editions.asked == [(token, poster.lower()), (token, "t-tmdb.12")]
    for odd in (f"{token}/../../etc/passwd", "short/x", f"{token}/a b", f"{token}"):
        assert await source.image(odd, None) is None
    assert len(editions.asked) == 2


async def test_an_articles_pictures_for_its_recipient() -> None:
    from portalab.modules.content.module import _EmailPictures

    reader, stranger = uuid4(), uuid4()
    mine = uuid4()

    class Content:
        async def read(self, asset: UUID, viewer: object) -> tuple[bytes, str]:
            if getattr(viewer, "user_id", None) != reader:
                raise LookupError("not theirs")
            return (JPEG, "image/jpeg") if asset == mine else (b"%PDF", "application/pdf")

    source = _EmailPictures(Content())
    assert await source.image(str(mine), reader) == JPEG
    assert await source.image(str(mine), stranger) is None  # what the recipient may not see stays out
    assert await source.image(str(mine), None) is None  # no recipient, no picture
    assert await source.image(str(uuid4()), reader) is None  # not a picture
    assert await source.image("not-a-uuid", reader) is None
