"""011 T005/T035 — CommonMark + GFM tables and task lists, callouts with an accessible title, code blocks,
Mermaid fences as an escaped placeholder, outline with unique anchors, collected internal links and assets,
plain text for search/AI, deterministic output; owner-tagged link-resolver and calendar-source registries;
textual diff segments; shared upload helper (sniffing, re-encoding)."""

import io

import pytest
from PIL import Image

from portalab.capabilities.content import (
    CalendarSourceRegistry,
    ContentError,
    ContentRef,
    LinkResolverRegistry,
)
from portalab.capabilities.content.render import RENDERER_VERSION, render_markdown
from portalab.core.uploads import UnsafeUpload, clean_upload, sanitize_filename, sniff
from portalab.modules.wiki.diffing import compare

SOURCE = """# Install
## Steps
## Steps
> [!TIP]
> Use **sudo**.

| Name | Port |
|:-----|-----:|
| web  | 80   |

- [x] download
- [ ] configure

```python
print("<hi>")
```

```mermaid
graph TD; A-->B
```

See [the FAQ](portalab://wiki/faq) and ![diagram](portalab-asset:0190f0a0-0000-7000-8000-00000000000a).
"""


def test_features() -> None:
    first, second = render_markdown(SOURCE), render_markdown(SOURCE)
    assert first == second and first.renderer_version == RENDERER_VERSION  # deterministic
    html = first.html
    assert '<div class="callout callout-tip" role="note" data-callout="tip">' in html
    assert '<p class="callout-title">Tip</p>' in html and "[!TIP]" not in html
    assert '<th style="text-align:left">Name</th>' in html and '<td style="text-align:right">80</td>' in html
    assert 'type="checkbox"' in html and 'disabled="disabled"' in html
    assert '<code class="language-python">print("&lt;hi&gt;")' in html
    assert '<pre class="mermaid-source" data-mermaid="true"><code>graph TD; A--&gt;B' in html
    expected = [(1, "h-install"), (2, "h-steps"), (2, "h-steps-2")]
    assert [(o.level, o.anchor) for o in first.outline] == expected
    assert first.links == ("portalab://wiki/faq",)
    assert first.assets == ("0190f0a0-0000-7000-8000-00000000000a",)
    assert "Use sudo" in first.text and "<" not in first.text.replace('print("<hi>")', "")
    assert render_markdown("password: hunter2hunter").warnings == ("possible_secret",)


def test_refs_and_registries() -> None:
    assert ContentRef.parse("portalab://wiki/faq") == ContentRef("wiki", "faq")
    assert ContentRef("news", "x").format() == "portalab://news/x"
    with pytest.raises(ContentError):
        ContentRef.parse("https://example.org")

    class R:
        kind = "radio"

        async def resolve(self, refs, viewer):  # type: ignore[no-untyped-def]
            return {}

    links = LinkResolverRegistry()
    links.register(R(), owner="plugin:radio")
    with pytest.raises(ContentError):
        links.register(R(), owner="module:other")
    assert links.unregister("plugin:radio") == 1 and links.get("radio") is None

    class S:
        kind = "radio"
        label_key = "radio:shows"

        async def items(self, start, end, viewer, ctx):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        async def item(self, source_id, viewer):  # type: ignore[no-untyped-def]
            return None

    sources = CalendarSourceRegistry()
    sources.register(S(), owner="plugin:radio")
    assert [s.kind for s in sources.all()] == ["radio"]
    assert sources.unregister("plugin:radio") == 1 and sources.all() == []


def test_compare_markers() -> None:
    diff = compare("alpha\nbeta\ngamma\n", "alpha\nBETA\ngamma\ndelta\n")
    assert [(d["op"], d["text"]) for d in diff["lines"]] == [
        ("equal", "alpha"),
        ("delete", "beta"),
        ("insert", "BETA"),
        ("equal", "gamma"),
        ("insert", "delta"),
    ]
    assert {d["op"] for d in diff["words"]} == {"equal", "insert", "delete"}


def _png_with_exif() -> bytes:
    image = Image.new("RGB", (40, 30), (200, 10, 10))
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"  # Make
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def test_upload_helper() -> None:
    jpeg = _png_with_exif()
    assert sniff(jpeg) == "image/jpeg"
    clean = clean_upload(jpeg, "../../holiday photo.jpeg")
    assert clean.content_type == "image/jpeg" and clean.filename == "holiday photo.jpg"
    assert b"SecretCamera" not in clean.data
    with pytest.raises(UnsafeUpload) as disguised:
        clean_upload(b"MZ\x90\x00" + b"\x00" * 64, "cute.png")  # a Windows executable renamed .png
    assert disguised.value.reason == "type"
    with pytest.raises(UnsafeUpload):
        clean_upload(b"", "x.png")
    with pytest.raises(UnsafeUpload):
        clean_upload(jpeg, "x.jpg", max_bytes=10)
    assert sanitize_filename('a<b>:c"|?*.txt') == "abc.txt"
