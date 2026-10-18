"""023 T004 — manifest validation: schema, semantic version and ranges, reserved/Admin-only and
non-namespaced permissions refused, non-namespaced events refused, personal data without an erasure
participant refused, unknown extension points refused, size limits."""

from typing import Any

import pytest

from portalab.modules.plugins.manifest.schema import InvalidManifest, parse_toml, validate

BASE: dict[str, Any] = {"key": "hello", "name": "Hello", "version": "1.2.3"}


def problems(**overrides: Any) -> list[str]:
    try:
        validate({**BASE, **overrides})
    except InvalidManifest as error:
        return list(error.extensions["problems"])
    return []


def test_valid_manifest() -> None:
    manifest = validate(
        {
            **BASE,
            "scope": "user",
            "requires_portal": ">=0.1,<2",
            "requires_plugins": [{"key": "base", "range": ">=1.0"}],
            "permissions": [{"name": "view", "description": "See it"}],
            "events": {"produces": ["greeted"], "consumes": ["user.verified"]},
            "extension_points": ["nav", "page"],
        }
    )
    assert manifest.permission_keys() == ["plugin:hello.view"]
    assert manifest.event_types() == ["plugin.hello.greeted"] and manifest.owner == "plugin:hello"


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"version": "1.0"}, "MAJOR.MINOR.PATCH"),
        ({"version": "banana"}, "semantic"),
        ({"requires_portal": "~~1"}, "invalid version range"),
        ({"requires_plugins": [{"key": "hello"}]}, "itself"),
        ({"permissions": [{"name": "users.manage", "description": "x"}]}, "namespaced"),
        ({"permissions": [{"name": "admin", "description": "x", "reserved": True}]}, "reserved"),
        ({"events": {"produces": ["user.created"]}}, "namespaced"),
        ({"personal_data": {"enabled": True}}, "erasure participant"),
        ({"extension_points": ["kernel_patch"]}, "unknown points"),
        ({"capabilities_provided": ["identity.directory"]}, "namespaced"),
    ],
)
def test_semantic_rules(overrides: dict[str, Any], fragment: str) -> None:
    assert any(fragment in p for p in problems(**overrides)), problems(**overrides)


def test_schema_and_size() -> None:
    assert problems(key="Bad Key")
    assert problems(surprise=True)
    assert problems(permissions=[{"name": f"p{i}", "description": "x"} for i in range(51)])
    with pytest.raises(InvalidManifest):
        parse_toml('key = "big"\n' + "#" * 70_000)
    with pytest.raises(InvalidManifest):
        parse_toml("key = [unclosed")


def test_shop_shelves() -> None:
    """030: a plugin names the shelf of the shop its own kinds of products are shown on, in one of the shop's
    departments; only kinds it sells, each on one shelf."""
    shelf = {"key": "bubbles", "department": "effects", "label_key": "plugin.hello:s", "types": ["bubble"]}
    v2 = {"schema_version": 2, "runtime": "declarative", "capabilities": {"product_types": ["bubble"]}}
    manifest = validate({**BASE, **v2, "shelves": [shelf]})
    assert manifest.shelves[0]["types"] == ["plugin:hello.bubble"]
    unsold = problems(**v2, shelves=[{**shelf, "types": ["x"]}])
    assert any("not one of its product_types" in p for p in unsold)
    assert any("another shelf" in p for p in problems(**v2, shelves=[shelf, {**shelf, "key": "again"}]))
    assert problems(**v2, shelves=[{**shelf, "department": "admin"}])
    assert any("schema_version = 2" in p for p in problems(shelves=[shelf]))
