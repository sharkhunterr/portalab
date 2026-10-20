"""Issue 171 — a source's card: a picture of the portal's own only (``/api/v1/…``; never another site's) and
a short line, shown beside the answer and never handed to the model."""

import json

from portalab.capabilities.ai import SourceRef, ToolResult
from portalab.modules.ai.attribution import source_dict
from portalab.modules.ai.context import frame_tool_result


def test_a_card_shows_the_portals_pictures_only_and_the_model_never_sees_them() -> None:
    poster = SourceRef(
        "media", "media:1", "Heat", url="/media/1", image="/api/v1/media/images/9", detail="1995"
    )
    card = source_dict(1, poster)
    assert card["image"] == "/api/v1/media/images/9" and card["detail"] == "1995"
    elsewhere = SourceRef("media", "media:2", "X", image="https://tracker.example/p.png")
    assert source_dict(2, elsewhere)["image"] is None
    framed = frame_tool_result("media.status", ToolResult("ok", {"title": "Heat"}), [card])
    payload = json.loads(framed.split("\n", 1)[1].rsplit("\n", 1)[0])
    assert payload["sources"] == [{k: v for k, v in card.items() if k not in ("image", "detail")}]
