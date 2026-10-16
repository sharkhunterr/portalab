"""022 T005/T008 (backend twin) — closed theme schema and accessibility floor, kept in step with the
design system: same built-in themes, same document keys as the shared JSON Schema."""

import json
from pathlib import Path

import pytest

from portalab.capabilities.visuals import interface_document
from portalab.modules.ui.themes.definition import contrast, floor_report, validate_definition

BACKEND = Path(__file__).resolve().parents[3]
BUILTIN = BACKEND / "src" / "portalab" / "modules" / "ui" / "themes"
FRONTEND = BACKEND.parent / "frontend" / "src" / "design-system" / "themes" / "builtin"


def _theme(key: str = "light") -> dict[str, object]:
    return interface_document(key)  # 028: from its pack


@pytest.mark.parametrize("key", ["orbit", "studio"])
def test_the_base_collection_s_interfaces_are_valid_and_pass_the_floor(key: str) -> None:
    theme, errors = validate_definition(_theme(key))
    assert errors == [] and theme is not None
    assert floor_report(theme)["violations"] == []


# 028: the socle's interfaces ship in the interface's code too (first paint): both copies identical
@pytest.mark.parametrize("key", ["portalab-dark", "portalab-light", "light", "dark", "high-contrast"])
def test_builtins_valid_pass_floor_and_match_frontend(key: str) -> None:
    theme, errors = validate_definition(_theme(key))
    assert errors == [] and theme is not None
    assert floor_report(theme)["violations"] == []
    assert _theme(key) == json.loads((FRONTEND / f"{key}.json").read_text(encoding="utf-8"))


def test_schema_keys_match_the_shared_json_schema() -> None:
    shared = json.loads((BUILTIN / "theme.schema.json").read_text(encoding="utf-8"))
    from portalab.modules.ui.themes.definition import ThemeDefinition

    assert set(shared["properties"]) == set(ThemeDefinition.model_fields)
    assert set(shared["properties"]["states"]["required"]) == {
        "loading",
        "available",
        "partial",
        "stale",
        "error",
        "unavailable",
        "maintenance",
        "unauthorized",
        "no-data",
        "syncing",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        {"css": "body{}"},
        {"colors": {**_theme()["colors"], "surface": "url(javascript:alert(1))"}},  # type: ignore[dict-item]
        {"background": {"image": "https://evil.example/x.png", "fallback": "#ffffff"}},
        {"background": {"image": "data:image/svg+xml;base64,PHN2Zz4=", "fallback": "#ffffff"}},
        {"sounds": {"alert": "https://evil.example/a.mp3"}},
        {"typography": {"fontFamily": "x;} body{display:none"}},
    ],
)
def test_inert_documents_only(mutation: dict[str, object]) -> None:
    assert validate_definition({**_theme(), **mutation})[1] != []


def test_missing_or_extra_state_rejected() -> None:
    states = dict(_theme()["states"])  # type: ignore[call-overload]
    states.pop("maintenance")
    assert validate_definition({**_theme(), "states": states})[1] != []
    extra = {**_theme()["states"], "celebrating": {"fg": "#000000", "bg": "#ffffff"}}  # type: ignore[dict-item]
    assert validate_definition({**_theme(), "states": extra})[1] != []


def test_contrast_reference_values() -> None:
    assert contrast("#000000", "#ffffff") == pytest.approx(21, abs=0.01)
    assert contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)
