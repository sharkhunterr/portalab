"""011 T004 — the shared Markdown pipeline renders every payload of the XSS/security corpus inert: no
script or event handler, no dangerous URL scheme, no embedded document, no style injection; external
links get ``rel`` and an external marker; external images are blocked by default; raw HTML is text."""

import re
from html.parser import HTMLParser

import pytest

from portalab.capabilities.content.render import render_markdown

CORPUS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)><circle/></svg>",
    "<math><mtext><table><mglyph><style><img src=x onerror=alert(1)>",
    "<iframe src='https://evil.example'></iframe>",
    "<object data='evil.swf'></object><embed src='evil'>",
    "<a href='javascript:alert(1)'>x</a>",
    "[click](javascript:alert(1))",
    "[click](JaVaScRiPt:alert(1))",
    "[click](  javascript:alert(1))",
    "[click](vbscript:msgbox(1))",
    "[click](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)",
    "![x](javascript:alert(1))",
    "![x](data:image/svg+xml;base64,PHN2ZyBvbmxvYWQ9YWxlcnQoMSk+)",
    "<div style='background:url(javascript:alert(1))'>x</div>",
    "<style>body{display:none}</style>",
    "<p onclick=alert(1)>hi</p>",
    "```html\n<script>alert(1)</script>\n```",
    "> [!NOTE]\n> <script>alert(1)</script>",
    "> [!WARNING] <img src=x onerror=alert(1)>",
    "<<script>script>alert(1)<</script>/script>",
    '<a href="https://ok.example" onmouseover="alert(1)">x</a>',
    '[x](https://ok.example "title" onmouseover=alert(1))',
    "| a |\n|---|\n| <img src=x onerror=alert(1)> |",
    "<details open ontoggle=alert(1)>",
    "<form action=javascript:alert(1)><button>x</button></form>",
    "<base href='https://evil.example/'>",
    "<meta http-equiv='refresh' content='0;url=https://evil.example'>",
    "[x](//evil.example/path)",
    '```mermaid\ngraph TD; A["<img src=x onerror=alert(1)>"]-->B\n```',
]
DANGEROUS_TAGS = {
    "script",
    "iframe",
    "object",
    "embed",
    "style",
    "svg",
    "math",
    "form",
    "base",
    "meta",
    "details",
    "link",
}
SAFE_SCHEMES = ("http://", "https://", "mailto:", "portalab://", "/", "#")


class Elements(HTMLParser):
    """Collects the real elements and attributes of rendered HTML (escaped text is ignored)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.found.append((tag, dict(attrs)))


def elements(html: str) -> list[tuple[str, dict[str, str | None]]]:
    parser = Elements()
    parser.feed(html)
    return parser.found


@pytest.mark.parametrize("source", CORPUS)
def test_payload_is_inert(source: str) -> None:
    html = render_markdown(source).html
    for tag, attrs in elements(html):
        assert tag not in DANGEROUS_TAGS, html
        assert not any(name.startswith("on") for name in attrs), html
        for name in ("href", "src", "action", "formaction", "xlink:href"):
            value = (attrs.get(name) or "").strip().lower()
            assert not value or value.startswith(SAFE_SCHEMES), html
        assert "style" not in attrs or re.fullmatch(
            r"text-align:\s*(left|right|center)", attrs["style"] or ""
        ), html


def test_links_and_images_policy() -> None:
    rendered = render_markdown(
        "[site](https://example.org) [page](portalab://wiki/getting-started) [rel](/news/x) "
        "![tracker](https://tracker.example/pixel.png)"
    )
    html = rendered.html
    assert 'rel="noopener noreferrer nofollow external"' in html and 'data-external="true"' in html
    assert 'data-ref="portalab://wiki/getting-started"' in html and 'href="/news/x"' in html
    assert "tracker.example" not in html and 'data-blocked-image="true"' in html
    assert rendered.links == ("portalab://wiki/getting-started",)
    allowed = render_markdown("![t](https://img.example/a.png)", allow_external_images=True).html
    assert 'src="https://img.example/a.png"' in allowed


def test_protocol_relative_and_raw_html_are_neutralized() -> None:
    html = render_markdown("[x](//evil.example/path) <b>bold</b>").html
    assert all(not (attrs.get("href") or "").startswith("//") for _, attrs in elements(html))
    assert "&lt;b&gt;bold&lt;/b&gt;" in html
