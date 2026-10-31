"""#299 — what a source says: RSS 2.0 (a picture as media:thumbnail, an enclosure or the first image of its
HTML), RSS 1.0 and Atom; the summary as plain text, cut short; a web page announcing its feed; a document
declaring entities refused."""

from datetime import UTC, datetime

import pytest

from portalab.modules.news.sources.fetch import is_public
from portalab.modules.news.sources.parse import NotAFeed, announced, parse, plain

RSS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Ciné &amp; Séries</title><link>https://example.org/</link>
<item><title>Dune : la suite</title><link>/news/dune</link><guid>dune-2</guid>
<description>&lt;p&gt;Denis Villeneuve &lt;b&gt;revient&lt;/b&gt;.&lt;/p&gt;</description>
<pubDate>Fri, 30 Oct 2026 09:00:00 +0100</pubDate><media:thumbnail url="https://cdn.example.org/d.jpg"/></item>
<item><title>Sans date</title><link>https://example.org/b</link>
<description>&lt;img src="/i/b.png"&gt; texte</description></item>
<item><title></title><link>https://example.org/empty</link></item>
</channel></rss>""".encode()

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title>
<link rel="alternate" href="https://blog.example.org/"/>
<entry><title>Un article</title><id>tag:blog,1</id><link rel="alternate" href="https://blog.example.org/1"/>
<updated>2026-10-29T12:00:00Z</updated><summary type="html">Bonjour</summary>
<link rel="enclosure" type="image/jpeg" href="https://blog.example.org/1.jpg"/></entry></feed>"""

RDF = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel rdf:about="https://old.example.org/"><title>Ancien</title><link>https://old.example.org/</link></channel>
<item rdf:about="https://old.example.org/1"><title>Premier</title><link>https://old.example.org/1</link>
<dc:date>2026-10-28T08:00:00+00:00</dc:date></item></rdf:RDF>"""


def test_rss_items_with_their_picture_and_plain_summary() -> None:
    feed = parse(RSS, "https://example.org/feed.xml")
    assert feed.title == "Ciné & Séries" and feed.site == "https://example.org/"
    first, second = feed.items  # the item without a title is left out
    assert first.guid == "dune-2" and first.link == "https://example.org/news/dune"
    assert first.summary == "Denis Villeneuve revient."
    assert first.image == "https://cdn.example.org/d.jpg"
    assert first.published == datetime(2026, 10, 30, 8, 0, tzinfo=UTC)
    assert second.guid == "https://example.org/b" and second.published is None
    assert second.image == "https://example.org/i/b.png"


def test_atom_and_rdf() -> None:
    atom = parse(ATOM, "https://blog.example.org/feed")
    (entry,) = atom.items
    assert (entry.guid, entry.link, entry.summary) == ("tag:blog,1", "https://blog.example.org/1", "Bonjour")
    assert entry.image == "https://blog.example.org/1.jpg"
    assert entry.published == datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    rdf = parse(RDF, "https://old.example.org/rss")
    assert [i.title for i in rdf.items] == ["Premier"] and rdf.items[0].published is not None


def test_what_is_not_a_feed_is_refused() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel><title>&a;</title>'
    bomb += b"</channel></rss>"
    with pytest.raises(NotAFeed):
        parse(bomb, "https://example.org/")
    with pytest.raises(NotAFeed):
        parse(b"<html><body>hello</body></html>", "https://example.org/")
    with pytest.raises(NotAFeed):
        parse(b"not xml at all", "https://example.org/")


def test_a_page_announces_its_feed() -> None:
    page = b'<html><head><link rel="alternate" type="application/rss+xml" href="/rss.xml"></head></html>'
    assert announced(page, "https://example.org/blog/") == "https://example.org/rss.xml"
    assert announced(b"<html><head></head></html>", "https://example.org/") is None


def test_plain_text_is_short_and_clean() -> None:
    text = plain("<p>" + "mot " * 200 + "</p><script>alert(1)</script>", 50)
    assert len(text) <= 50 and text.endswith("…") and "<" not in text and "alert" not in text


def test_only_public_addresses() -> None:
    assert is_public("93.184.216.34")
    for private in ("127.0.0.1", "192.168.1.87", "10.0.0.1", "::1", "::ffff:192.168.1.1", "169.254.169.254"):
        assert not is_public(private)


YOUTUBE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/"
 xmlns="http://www.w3.org/2005/Atom"><title>Bandes-annonces</title>
<entry><id>yt:video:abc</id><title>DUNE 3 Bande Annonce VF</title>
<link rel="alternate" href="https://www.youtube.com/watch?v=abc"/><published>2026-10-31T10:00:00+00:00</published>
<media:group><media:title>DUNE 3</media:title><media:thumbnail url="https://i1.ytimg.com/vi/abc/hqdefault.jpg"/>
<media:description>La suite de la saga.</media:description></media:group></entry></feed>"""


def test_a_youtube_channel() -> None:
    (video,) = parse(YOUTUBE, "https://www.youtube.com/feeds/videos.xml?channel_id=x").items
    assert video.link == "https://www.youtube.com/watch?v=abc" and video.summary == "La suite de la saga."
    assert video.image == "https://i1.ytimg.com/vi/abc/hqdefault.jpg"
