"""027 T008 — theme v2 (backend twin): layout/motion/sound vocabulary incl. principle-changing arrangements,
unknown values refused with their path, v1 upgraded on validation, floor on gamification accents."""

import pytest

from portalab.capabilities.visuals import interface_document
from portalab.modules.ui.themes.definition import SCHEMA_VERSION, floor_report, validate_definition


def _theme(key: str) -> dict[str, object]:
    return interface_document(key)  # 028: from its pack


def test_principle_changing_arrangements_are_accepted() -> None:
    document = {
        **_theme("portalab-dark"),
        "layout": {
            "nav": {"desktop": "orbit", "tablet": "orbit", "phone": "orbit"},
            "headerPosition": "bottom",
            "cards": "outlined",
        },
        "motion": {"profile": "playful", "celebration": "glow"},
    }
    theme, errors = validate_definition(document)
    assert errors == [] and theme is not None and theme.layout is not None
    assert theme.layout.headerPosition == "bottom" and theme.layout.nav is not None
    assert theme.layout.nav.phone == "orbit"


@pytest.mark.parametrize(
    ("mutation", "path"),
    [
        ({"layout": {"nav": {"desktop": "floating"}}}, "layout.nav.desktop"),
        ({"layout": {"grid": "masonry"}}, "layout.grid"),
        ({"motion": {"profile": "wild"}}, "motion.profile"),
        ({"sounds": {"boom": "asset:x.wav"}}, "sounds.boom"),
        ({"sounds": {"levelUp": "https://evil.example/a.mp3"}}, "sounds.levelUp"),
    ],
)
def test_unknown_values_are_refused_with_their_path(mutation: dict[str, object], path: str) -> None:
    errors = validate_definition({**_theme("portalab-dark"), **mutation})[1]
    assert any(e.startswith(path) for e in errors), errors


def test_v1_documents_are_upgraded() -> None:
    theme, errors = validate_definition(_theme("light"))
    assert errors == [] and theme is not None
    assert theme.schemaVersion == SCHEMA_VERSION and theme.layout is None


def test_floor_covers_gamification_accents() -> None:
    document = _theme("portalab-light")
    colors = dict(document["colors"])  # type: ignore[call-overload]
    colors["rarity"] = {**colors["rarity"], "legendary": "#fff8e0"}
    theme, _ = validate_definition({**document, "colors": colors})
    assert theme is not None
    report = floor_report(theme)
    assert report["ok"] is False
    assert any("rarity.legendary" in v for v in report["violations"])  # type: ignore[attr-defined]
