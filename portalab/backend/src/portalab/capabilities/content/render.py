"""``MarkdownRenderer`` (spec 011 T007; R2-R5): the single trust boundary for user-authored content.

Markdown (CommonMark + GFM tables, strikethrough, task lists, GitHub-style callouts ``> [!NOTE]``, fenced
code and ``mermaid`` fences) is rendered **server-side** with raw HTML disabled, then sanitized by ``nh3``
with a strict allowlist. Rules:

* links: ``http(s)``, ``mailto``, relative paths and ``portalab://kind/id`` refs only; external links get
  ``rel="noopener noreferrer nofollow external"`` and ``data-external``; portal refs keep the author's text
  and are resolved per viewer at display time (never baked into the cache);
* images: only portal assets (``portalab-asset:<id>``); external images are blocked unless allowed;
* ``mermaid`` fences become an inert ``<pre data-mermaid>`` placeholder rendered client-side in strict mode;
* headings get stable ids (``h-…``) and an outline; links/assets are collected; plain text is extracted
  for search and AI.
Output is deterministic for a given ``RENDERER_VERSION``.
"""

import html
import re
import threading
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import anyio
import nh3
from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from mdit_py_plugins.tasklists import tasklists_plugin

RENDERER_VERSION = "1"
ASSET_SCHEME = "portalab-asset:"
REF_SCHEME = "portalab://"
CALLOUTS = {
    "NOTE": "Note",
    "TIP": "Tip",
    "IMPORTANT": "Important",
    "WARNING": "Warning",
    "CAUTION": "Caution",
}
_CALLOUT = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*\n?", re.IGNORECASE)
_SECRET_HINT = re.compile(
    r"(?i)\b(pass(word|wd)?|secret|api[_-]?key|token|private[_-]?key)\b\s*[:=]\s*\S{6,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)

TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "del", "s", "code", "pre",
    "blockquote", "ul", "ol", "li", "a", "img", "table", "thead", "tbody", "tr", "th", "td", "input",
    "span", "div",
}  # fmt: skip
ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title", "rel", "data-ref", "data-external", "class"},
    "img": {"src", "alt", "title", "data-asset"},
    "code": {"class"},
    "pre": {"class", "data-mermaid"},
    "th": {"style"},
    "td": {"style"},
    "input": {"type", "checked", "disabled", "class"},
    "li": {"class"},
    "ul": {"class"},
    "div": {"class", "role", "data-callout"},
    "p": {"class"},
    "span": {"class", "data-blocked-image"},
    **{f"h{n}": {"id"} for n in range(1, 7)},
}
URL_SCHEMES = {"http", "https", "mailto", "portalab"}


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    level: int
    text: str
    anchor: str


@dataclass(frozen=True, slots=True)
class RenderedContent:
    html: str
    text: str
    outline: tuple[OutlineEntry, ...] = ()
    links: tuple[str, ...] = ()  # ``portalab://`` refs
    external_links: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()  # asset ids
    warnings: tuple[str, ...] = ()  # non-blocking (e.g. something that looks like a secret)
    renderer_version: str = RENDERER_VERSION


MAX_OUTLINE = 1000  # #274: a table of contents longer than this helps no one


@dataclass
class _State:
    allow_external_images: bool
    links: list[str] = field(default_factory=list)
    external: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    outline: list[OutlineEntry] = field(default_factory=list)
    anchors: set[str] = field(default_factory=set)
    suffixes: dict[str, int] = field(default_factory=dict)  # #274: the next number tried for a repeated id


def _slug(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")[:60] or "section"


def _is_external(href: str) -> bool:
    return href.lower().startswith(("http://", "https://"))


def _safe_href(href: str) -> str | None:
    value = href.strip()
    lowered = value.lower()
    if lowered.startswith("//") or "\\" in lowered:
        return None  # protocol-relative or backslash tricks: never a relative path
    if lowered.startswith(REF_SCHEME) or lowered.startswith(("http://", "https://", "mailto:")):
        return value
    if lowered.startswith(("/", "#", "?")) and not lowered.startswith("//"):
        return value
    if ":" not in value.split("/", 1)[0]:
        return value  # plain relative path
    return None


class MarkdownRenderer:
    def __init__(self) -> None:
        md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
        md.enable(["table", "strikethrough"])
        md.use(tasklists_plugin)
        md.validateLink = lambda url: True  # type: ignore[method-assign]  # our own allowlist applies below
        self.renderer: RendererHTML = md.renderer  # type: ignore[assignment]
        rules: Any = self.renderer.rules
        rules["link_open"] = self._link_open
        rules["image"] = self._image
        rules["fence"] = self._fence
        rules["heading_open"] = self._heading_open
        self.md = md

    # --- render rules --------------------------------------------------------------------------------
    def _link_open(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        token = tokens[idx]
        state: _State = env["state"]
        href = _safe_href(str(token.attrGet("href") or ""))
        attrs: dict[str, str] = {}
        if href is None:
            return "<a>"
        if href.lower().startswith(REF_SCHEME):
            state.links.append(href)
            attrs = {"href": href, "data-ref": href, "class": "content-ref"}
        elif _is_external(href):
            state.external.append(href)
            attrs = {
                "href": href,
                "rel": "noopener noreferrer nofollow external",
                "data-external": "true",
                "class": "external-link",
            }
        else:
            attrs = {"href": href}
        if token.attrGet("title"):
            attrs["title"] = str(token.attrGet("title"))
        inner = " ".join(f'{k}="{html.escape(v, quote=True)}"' for k, v in attrs.items())
        return f"<a {inner}>"

    def _image(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        token = tokens[idx]
        state: _State = env["state"]
        src = str(token.attrGet("src") or "").strip()
        alt = html.escape(self.renderer.renderInlineAsText(token.children or [], options, env), quote=True)
        if src.lower().startswith(ASSET_SCHEME):
            asset = re.sub(r"[^0-9a-fA-F-]", "", src[len(ASSET_SCHEME) :])[:36]
            if asset:
                state.assets.append(asset)
                return f'<img src="/api/v1/content/assets/{asset}" alt="{alt}" data-asset="{asset}">'
        if _is_external(src) and state.allow_external_images:
            state.external.append(src)
            return f'<img src="{html.escape(src, quote=True)}" alt="{alt}">'
        return f'<span class="blocked-image" data-blocked-image="true">{alt or "image"}</span>'

    def _fence(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        token = tokens[idx]
        info = (token.info or "").strip().split(" ", 1)[0].lower()
        source = html.escape(token.content)
        if info == "mermaid":
            return f'<pre class="mermaid-source" data-mermaid="true"><code>{source}</code></pre>\n'
        language = re.sub(r"[^a-z0-9_+-]", "", info)[:24]
        css = f' class="language-{language}"' if language else ""
        return f"<pre><code{css}>{source}</code></pre>\n"

    def _heading_open(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        token = tokens[idx]
        state: _State = env["state"]
        inline = tokens[idx + 1]
        text = self.renderer.renderInlineAsText(inline.children or [], options, env).strip()
        anchor = f"h-{_slug(text)}"
        if anchor in state.anchors:  # #274: numbered from where the last repeat stopped — never from 2 again
            base, n = anchor, state.suffixes.get(anchor, 2)
            while (anchor := f"{base}-{n}") in state.anchors:
                n += 1
            state.suffixes[base] = n + 1
        state.anchors.add(anchor)
        if len(state.outline) < MAX_OUTLINE:
            state.outline.append(OutlineEntry(int(token.tag[1]), text[:200], anchor))
        return f'<{token.tag} id="{anchor}">'

    # --- callouts (token rewrite) -------------------------------------------------------------------------
    @staticmethod
    def _callouts(tokens: list[Token]) -> list[Token]:
        out: list[Token] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if (
                token.type == "blockquote_open"
                and i + 2 < len(tokens)
                and tokens[i + 1].type == "paragraph_open"
                and tokens[i + 2].type == "inline"
            ):
                inline = tokens[i + 2]
                match = _CALLOUT.match(inline.content)
                if match:
                    kind = match.group(1).upper()
                    token.tag = "div"
                    token.attrs = {
                        "class": f"callout callout-{kind.lower()}",
                        "role": "note",
                        "data-callout": kind.lower(),
                    }
                    depth, j = 0, i
                    while j < len(tokens):
                        if tokens[j].type == "blockquote_open":
                            depth += 1
                        elif tokens[j].type == "blockquote_close":
                            depth -= 1
                            if depth == 0:
                                tokens[j].tag = "div"
                                break
                        j += 1
                    inline.content = inline.content[match.end() :]
                    if inline.children:
                        first = inline.children[0]
                        if first.type == "text":
                            first.content = _CALLOUT.sub("", first.content, count=1)
                        while (inline.children and inline.children[0].type in ("softbreak", "hardbreak")) or (
                            inline.children
                            and inline.children[0].type == "text"
                            and not inline.children[0].content
                        ):
                            inline.children.pop(0)
                    title_open = Token("paragraph_open", "p", 1, attrs={"class": "callout-title"}, block=True)
                    title = Token(
                        "inline",
                        "",
                        0,
                        content=CALLOUTS[kind],
                        children=[Token("text", "", 0, content=CALLOUTS[kind])],
                    )
                    title_close = Token("paragraph_close", "p", -1, block=True)
                    out.extend([token, title_open, title, title_close])
                    i += 1
                    continue
            out.append(token)
            i += 1
        return out

    @staticmethod
    def _plain(tokens: Sequence[Token]) -> str:
        parts: list[str] = []
        for token in tokens:
            if token.type == "inline":
                parts.append(
                    "".join(c.content for c in token.children or [] if c.type in ("text", "code_inline"))
                )
            elif token.type in ("fence", "code_block"):
                parts.append(token.content)
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    def render(self, source: str, *, allow_external_images: bool = False) -> RenderedContent:
        state = _State(allow_external_images=allow_external_images)
        env: dict[str, Any] = {"state": state}
        tokens = self._callouts(self.md.parse(source, env))
        raw = self.renderer.render(tokens, self.md.options, env)
        clean = nh3.clean(
            raw,
            tags=TAGS,
            attributes=ATTRIBUTES,
            url_schemes=URL_SCHEMES,
            link_rel=None,
            strip_comments=True,
            filter_style_properties={"text-align"},
        )
        warnings = ("possible_secret",) if _SECRET_HINT.search(source) else ()
        return RenderedContent(
            html=clean,
            text=self._plain(tokens)[:100_000],
            outline=tuple(state.outline),
            links=tuple(dict.fromkeys(state.links)),
            external_links=tuple(dict.fromkeys(state.external)),
            assets=tuple(dict.fromkeys(state.assets)),
            warnings=warnings,
        )


_local = threading.local()  # #274: one renderer per thread (documents are rendered off the event loop)


def render_markdown(source: str, *, allow_external_images: bool = False) -> RenderedContent:
    renderer: MarkdownRenderer | None = getattr(_local, "renderer", None)
    if renderer is None:
        renderer = _local.renderer = MarkdownRenderer()
    return renderer.render(source, allow_external_images=allow_external_images)


async def render_markdown_async(source: str, *, allow_external_images: bool = False) -> RenderedContent:
    """#274: :func:`render_markdown` in a worker thread — a long document takes a second or two, the server
    answers everyone else meanwhile."""
    return await anyio.to_thread.run_sync(
        partial(render_markdown, source, allow_external_images=allow_external_images)
    )


_HEADING = re.compile(r'<h([1-6]) id="(h-[a-z0-9-]+)">(.*?)</h\1>', re.S)
_TAG = re.compile(r"<[^>]*>")


def outline_of(rendered_html: str) -> tuple[OutlineEntry, ...]:
    """#274: the outline of an already rendered document, read from its headings (linear — a page shown is
    never rendered again just for its table of contents)."""
    entries: list[OutlineEntry] = []
    for match in _HEADING.finditer(rendered_html):
        text = html.unescape(_TAG.sub("", match.group(3))).strip()
        entries.append(OutlineEntry(int(match.group(1)), text[:200], match.group(2)))
        if len(entries) >= MAX_OUTLINE:
            break
    return tuple(entries)
