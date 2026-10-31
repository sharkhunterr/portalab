"""#299: lists of sources as OPML — the format every feed reader exports and imports (each source an
``<outline xmlUrl=… text=…>``, nested in folders or not)."""

from collections.abc import Sequence
from xml.sax.saxutils import escape, quoteattr

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_OUTLINES = 500


class NotOpml(ValueError):
    """Not an OPML list."""


def read_opml(text: str) -> list[tuple[str, str]]:
    """The sources an OPML list holds: ``(name, address)``, http(s) only, each once."""
    try:
        root = SafeET.fromstring(text.encode("utf-8"), forbid_entities=True, forbid_external=True)
    except (DefusedXmlException, SafeET.ParseError) as exc:
        raise NotOpml("not an OPML list") from exc
    if root.tag.lower() != "opml":
        raise NotOpml("not an OPML list")
    found: dict[str, str] = {}
    for node in root.iter("outline"):
        url = (node.get("xmlUrl") or node.get("xmlurl") or "").strip()
        if url.startswith(("http://", "https://")) and len(url) <= 1000 and url not in found:
            found[url] = (node.get("title") or node.get("text") or "").strip()[:120]
        if len(found) >= MAX_OUTLINES:
            break
    return [(name, url) for url, name in found.items()]


def write_opml(title: str, sources: Sequence[tuple[str, str, str | None]]) -> str:
    """``(name, feed address, site address)`` as an OPML list."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        f"  <head><title>{escape(title)}</title></head>",
        "  <body>",
    ]
    for name, url, site in sources:
        attrs = f'type="rss" text={quoteattr(name)} title={quoteattr(name)} xmlUrl={quoteattr(url)}'
        if site:
            attrs += f" htmlUrl={quoteattr(site)}"
        lines.append(f"    <outline {attrs}/>")
    lines += ["  </body>", "</opml>"]
    return "\n".join(lines) + "\n"
