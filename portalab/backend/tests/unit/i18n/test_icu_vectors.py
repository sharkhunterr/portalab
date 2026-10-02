"""026 T004/T009 — the shared golden ICU vectors render identically on the backend (pure Python + Babel);
syntax errors are reported; rendering never raises on missing arguments."""

import json
from pathlib import Path

import pytest

from portalab.modules.i18n.render.icu import MessageSyntaxError, parse, render

VECTORS = json.loads(
    (Path(__file__).resolve().parents[2] / "data" / "icu_vectors.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: f"{v['locale']}:{v['message'][:30]}")
def test_golden_vector(vector: dict[str, object]) -> None:
    assert render(str(vector["message"]), vector["args"], str(vector["locale"])) == vector["expected"]  # type: ignore[arg-type]


def test_missing_argument_never_raises() -> None:
    assert (
        render("Hi {name}, {count, plural, one {# item} other {# items}}", {}, "en") == "Hi {name}, {count}"
    )


@pytest.mark.parametrize(
    "message",
    [
        "{count, plural, one {x}}",
        "{count, plural, other {x}",
        "Unbalanced }",
        "{x, currency}",
        "{x, select, a {1} b {2}}",
    ],
)
def test_invalid_messages(message: str) -> None:
    with pytest.raises(MessageSyntaxError):
        parse(message)


def test_markup_is_plain_text() -> None:
    assert (
        render("{x}", {"x": "<script>alert(1)</script>"}, "en") == "<script>alert(1)</script>"
    )  # escaped by the UI
