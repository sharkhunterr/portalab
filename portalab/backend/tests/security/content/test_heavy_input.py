"""#274: what a member writes or sends never holds the server — a document repeating one heading thousands
of times renders in linear time (same ids as before), off the event loop; an image that unfolds into too
many pixels is refused before it is decoded."""

import asyncio
import io
import time

import pytest
from PIL import Image

from portalab.capabilities.content.render import outline_of, render_markdown, render_markdown_async
from portalab.core.uploads import UnsafeUpload, clean_upload


def test_a_repeated_heading_renders_in_linear_time() -> None:
    started = time.monotonic()
    rendered = render_markdown("# a\n" * 20_000)
    assert time.monotonic() - started < 5  # quadratic: 200 million tries
    assert [o.anchor for o in rendered.outline[:3]] == ["h-a", "h-a-2", "h-a-3"]
    assert len(rendered.outline) == 1000  # the table of contents is bounded


def test_numbered_ids_stay_unique_and_as_before() -> None:
    anchors = [o.anchor for o in render_markdown("## a\n## a\n## a-2\n## a\n").outline]
    assert anchors == ["h-a", "h-a-2", "h-a-2-2", "h-a-3"]


def test_the_outline_is_read_from_the_rendered_page() -> None:
    rendered = render_markdown("# Intro & *more*\n## a\n## a\n")
    assert outline_of(rendered.html) == rendered.outline


async def test_rendering_leaves_the_event_loop_free() -> None:
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    ticker = asyncio.create_task(tick())
    await render_markdown_async("[" * 200_000)  # about a second of work
    ticker.cancel()
    assert ticks > 5


def test_an_image_of_too_many_pixels_is_refused() -> None:
    out = io.BytesIO()
    Image.new("1", (8000, 6000)).save(out, format="PNG")  # 48 Mpx in a few kB
    with pytest.raises(UnsafeUpload) as caught:
        clean_upload(out.getvalue(), "bomb.png")
    assert caught.value.reason == "too_large"


def test_another_decoder_never_reads_a_member_file() -> None:
    out = io.BytesIO()
    Image.new("RGB", (8, 8)).save(out, format="TIFF")
    with pytest.raises(UnsafeUpload):
        clean_upload(out.getvalue(), "x.tif")
