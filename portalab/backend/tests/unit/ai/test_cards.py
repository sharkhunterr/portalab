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


def test_an_answer_citing_nothing_still_shows_what_the_portal_handed_it() -> None:
    from portalab.modules.ai.attribution import UNCITED_CARDS, Attributor

    attributor = Attributor()
    titles = [SourceRef("media", f"media:{i}", f"Film {i}", url=f"/media/{i}") for i in range(10)]
    attributor.add("media.search_catalog", ToolResult("ok", {}, titles))
    _, sources, interpretation = attributor.finalize("Three films are here.")
    assert [s["title"] for s in sources] == [f"Film {i}" for i in range(UNCITED_CARDS)] and not interpretation
    _, cited, _ = attributor.finalize("Film 3 is here [4].")
    assert [s["n"] for s in cited] == [4]  # cited: only those
    assert Attributor().finalize("Hello.")[2] is True  # no portal data: the assistant's interpretation
