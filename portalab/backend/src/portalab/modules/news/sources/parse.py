"""#299: what a source says — RSS 2.0, RSS 1.0 (RDF) and Atom, read by defusedxml (a document declaring
entities or pointing elsewhere is refused: nothing ever expands). Each item: its id, link, title, a short
plain-text summary (its HTML stripped), a picture's address and its date. A web page instead of a feed:
the feed it announces (``<link rel="alternate">``)."""

import html
import re
import xml.etree.ElementTree as ET  # the element type only: documents are read by defusedxml
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import nh3
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

SUMMARY = 300
TITLE = 300
MAX_ITEMS = 100
MEDIA = "{http://search.yahoo.com/mrss/}"
_SPACES = re.compile(r"\s+")
_IMG = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_ALTERNATE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r"([a-zA-Z-]+)\s*=\s*[\"']([^\"']*)[\"']")
FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/rdf+xml", "application/feed+json")


class NotAFeed(ValueError):
    """Neither a feed nor a page announcing one."""


@dataclass(frozen=True, slots=True)
class ParsedItem:
    guid: str
    link: str
    title: str
    summary: str
    image: str | None
    published: datetime | None


@dataclass(frozen=True, slots=True)
class ParsedFeed:
    title: str
    site: str | None
    items: list[ParsedItem] = field(default_factory=list)


def plain(text: str | None, limit: int = SUMMARY) -> str:
    """HTML (or text) as a short plain sentence: no tag, entities decoded, cut at a word."""
    if not text:
        return ""
    flat = _SPACES.sub(" ", html.unescape(nh3.clean(text, tags=set()))).strip()
    if len(flat) <= limit:
        return flat
    cut = flat[: limit - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def announced(page: bytes, base: str) -> str | None:
    """The feed a web page announces, if any."""
    # the whole page (fetched within its limit): a YouTube channel's page names its feed far down
    text = page.decode("utf-8", errors="replace")
    for tag in _ALTERNATE.findall(text):
        attrs = {k.lower(): v for k, v in _ATTR.findall(tag)}
        alternate = "alternate" in attrs.get("rel", "").lower()
        if alternate and attrs.get("type", "").lower() in FEED_TYPES and attrs.get("href"):
            return urljoin(base, html.unescape(attrs["href"]))
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child(node: ET.Element, *names: str) -> ET.Element | None:
    for child in node:
        if _local(child.tag) in names:
            return child
    return None


def _text(node: ET.Element, *names: str) -> str:
    child = _child(node, *names)
    return "".join(child.itertext()).strip() if child is not None else ""


def _date(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _image(node: ET.Element, body: str) -> str | None:
    for child in node.iter():
        tag, kind = child.tag, child.get("type", "")
        if tag == f"{MEDIA}thumbnail" and child.get("url"):
            return child.get("url")
        if (
            tag == f"{MEDIA}content"
            and child.get("url")
            and (child.get("medium") == "image" or "image" in kind)
        ):
            return child.get("url")
        if _local(tag) == "enclosure" and kind.startswith("image/"):
            return child.get("url") or child.get("href")
        if _local(tag) == "link" and child.get("rel") == "enclosure" and kind.startswith("image"):
            return child.get("href")
    found = _IMG.search(body)
    return html.unescape(found.group(1)) if found else None


def _rss_item(node: ET.Element, base: str) -> ParsedItem | None:
    link = _text(node, "link") or (node.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about") or "")
    body = _text(node, "encoded") or _text(node, "description")
    title = plain(_text(node, "title"), TITLE)
    guid = _text(node, "guid") or link or title
    if not title or not guid:
        return None
    image = _image(node, body)
    return ParsedItem(
        guid=guid[:500],
        link=urljoin(base, link) if link else base,
        title=title,
        summary=plain(body),
        image=urljoin(base, image) if image else None,
        published=_date(_text(node, "pubDate", "date")),
    )


def _atom_link(node: ET.Element) -> str:
    fallback = ""
    for child in node:
        if _local(child.tag) == "link" and child.get("href"):
            if child.get("rel", "alternate") == "alternate":
                return child.get("href", "")
            fallback = fallback or child.get("href", "")
    return fallback


def _nested(node: ET.Element, tag: str) -> str:
    """A nested element's text — a YouTube video's ``media:group/media:description``."""
    found = node.find(f".//{tag}")
    return "".join(found.itertext()).strip() if found is not None else ""


def _atom_item(node: ET.Element, base: str) -> ParsedItem | None:
    link = _atom_link(node)
    body = _text(node, "content") or _text(node, "summary") or _nested(node, f"{MEDIA}description")
    title = plain(_text(node, "title"), TITLE)
    guid = _text(node, "id") or link or title
    if not title or not guid:
        return None
    image = _image(node, body)
    return ParsedItem(
        guid=guid[:500],
        link=urljoin(base, link) if link else base,
        title=title,
        summary=plain(body),
        image=urljoin(base, image) if image else None,
        published=_date(_text(node, "published") or _text(node, "updated")),
    )


def parse(body: bytes, base: str) -> ParsedFeed:
    try:
        root = SafeET.fromstring(body, forbid_dtd=False, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as exc:
        raise NotAFeed("a document declaring entities") from exc
    except ET.ParseError as exc:
        raise NotAFeed("not a feed") from exc
    kind = _local(root.tag)
    if kind == "feed":  # Atom
        items = [_atom_item(e, base) for e in root if _local(e.tag) == "entry"]
        site = _atom_link(root) or None
        return ParsedFeed(plain(_text(root, "title"), 120), site, [i for i in items if i][:MAX_ITEMS])
    if kind in ("rss", "RDF"):
        channel = _child(root, "channel")
        if channel is None:
            raise NotAFeed("not a feed")
        holder = channel if kind == "rss" else root
        items = [_rss_item(e, base) for e in holder if _local(e.tag) == "item"]
        site = _text(channel, "link") or None
        return ParsedFeed(plain(_text(channel, "title"), 120), site, [i for i in items if i][:MAX_ITEMS])
    raise NotAFeed("not a feed")
