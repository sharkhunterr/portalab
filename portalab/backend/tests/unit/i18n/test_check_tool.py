"""026 T010 / quickstart 6 — ``portalab i18n check`` passes on the shipped bundles and fails when a
translation drops a placeholder, breaks ICU syntax, misses a key or adds an unknown one; pseudo-locales keep
ICU syntax valid."""

import json
from pathlib import Path

from portalab.modules.i18n.catalog.service import LOCALES_DIR
from portalab.modules.i18n.render.icu import parse
from portalab.modules.i18n.tools.check import check, pseudo


def write(root: Path, language: str, messages: dict[str, str]) -> None:
    (root / language).mkdir(exist_ok=True)
    (root / language / "core.json").write_text(json.dumps(messages), encoding="utf-8")


def test_shipped_bundles_are_clean() -> None:
    assert check(LOCALES_DIR) == []


def test_problems_are_reported(tmp_path: Path) -> None:
    write(tmp_path, "en", {"hello": "Hello {name}", "items": "{count, plural, one {# item} other {# items}}"})
    write(tmp_path, "fr", {"hello": "Bonjour", "extra": "x", "items": "{count, plural, one {# élément}"})
    problems = "\n".join(check(tmp_path))
    assert "fr/core:hello: placeholders" in problems
    assert "fr/core:items: invalid ICU message" in problems
    assert "fr/core:extra: unused" in problems
    write(tmp_path, "fr", {"hello": "Bonjour {name}"})
    assert check(tmp_path) == ["fr/core:items: missing translation"]


def test_pseudo_keeps_syntax() -> None:
    for namespaces in (pseudo(LOCALES_DIR, "en-XA"), pseudo(LOCALES_DIR, "ar-XB")):
        for messages in namespaces.values():
            for message in messages.values():
                parse(message)
