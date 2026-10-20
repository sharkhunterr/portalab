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


def test_the_language_a_question_is_written_in() -> None:
    from portalab.modules.ai.context import language_of

    assert language_of("Est ce que tous les services fonctionnent ?") == "French"
    assert language_of("Pourquoi ce film a un badge leaving soon") == "French"
    assert language_of("Are all the services working?") == "English"
    assert language_of("Heat") is None


def test_the_assistant_says_who_it_is_what_it_is_for_and_what_to_do_without_an_answer() -> None:
    from portalab.modules.ai.context import DEFAULT_FALLBACK, system_prompt
    from portalab.modules.ai.settings import AiConfig

    config = AiConfig()  # the settings' own values: « Nova », its role, what to do without an answer
    assert config.assistant_name == "Nova"
    plain = system_prompt(
        "fr", None, None, {"name": config.assistant_name, "role": config.assistant_role, "fallback": ""}
    )
    assert plain.startswith("Your name is Nova, the friendly assistant of this portal: you help the members")
    assert system_prompt("fr", None).startswith("Your name is Assistant,")  # a name emptied: a neutral one
    assert "introduce yourself warmly" in plain  # « who are you? » needs no tool
    assert DEFAULT_FALLBACK in plain and "support ticket" in plain
    told = system_prompt(
        "fr",
        None,
        None,
        {
            "name": "Xeno",
            "site": "Xenoportal",
            "role": "guide the members of the Xeno family {through} their media.",
            "fallback": "send them to the wiki's FAQ",
        },
    )
    assert told.startswith('Your name is Xeno, the friendly assistant of "Xenoportal": you guide the members')
    assert "(through)" in told and "{through}" not in told  # an administrator's braces never break the prompt
    assert "When your tools do not hold the answer: send them to the wiki's FAQ." in told


def test_questions_about_the_assistant_need_no_lookup() -> None:
    from portalab.capabilities.ai import ChatMessage
    from portalab.modules.ai.orchestrator import needs_lookup

    assert not needs_lookup([ChatMessage("user", "Bonjour, qui es-tu exactement ?")])
    assert not needs_lookup([ChatMessage("user", "Dis-moi ce que tu sers à quoi au juste")])
    assert needs_lookup([ChatMessage("user", "Est-ce que Plex fonctionne en ce moment ?")])
