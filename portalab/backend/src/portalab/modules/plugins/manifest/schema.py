"""Plugin manifest (T008; R5): ``plugin.toml`` validated by a JSON Schema, then by semantic rules —
semantic version and version ranges, namespaced permissions (``plugin:<key>.<name>``, never reserved) and
events (``plugin.<key>.<name>``), personal data only with an erasure participant, only the official
extension points (plugins cannot define new ones), bounded sizes."""

import re
import tomllib
from dataclasses import dataclass, field
from typing import Any

import jsonschema
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from portalab.core.errors import ValidationFailed

MAX_BYTES = 64 * 1024
KEY = r"^[a-z][a-z0-9_]{1,39}$"
NAME = r"^[a-z][a-z0-9_]{0,47}$"
EXTENSION_POINTS = (
    "nav",
    "page",
    "widget",
    "action",
    "search",
    "calendar",
    "statistics",
    "automation_action",
    "automation_trigger",
    "ai_tool",
    "notification_category",
    "theme",
    "i18n",
    "permission",
    "setting",
    "event_type",
    "capability",
    "product_type",
    "media_type",
    "profile_section",
    "discovery_shelf",
    "connector",
    "route",
)
_LIST = {"type": "array", "maxItems": 50}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["key", "name", "version"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [1]},
        "key": {"type": "string", "pattern": KEY},
        "name": {"type": "string", "minLength": 1, "maxLength": 120},
        "description": {"type": "string", "maxLength": 1000},
        "version": {"type": "string", "maxLength": 64},
        "scope": {"enum": ["portal", "user"]},
        "maturity": {"enum": ["experimental", "beta", "stable", "deprecated"]},
        "deprecation_notice": {"type": "string", "maxLength": 300},
        "requires_portal": {"type": "string", "maxLength": 64},
        "entry_point": {
            "type": "string",
            "pattern": r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*:[a-z_][a-z0-9_]*$",
        },
        "requires_capabilities": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "maxLength": 96},
                    "range": {"type": "string", "maxLength": 64},
                },
            },
        },
        "requires_plugins": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key"],
                "properties": {
                    "key": {"type": "string", "pattern": KEY},
                    "range": {"type": "string", "maxLength": 64},
                },
            },
        },
        "extension_points": {**_LIST, "items": {"type": "string"}},
        "permissions": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "description"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string", "maxLength": 200},
                    "reserved": {"type": "boolean"},
                },
            },
        },
        "settings": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "type", "default"],
                "properties": {
                    "name": {"type": "string", "pattern": NAME},
                    "type": {"enum": ["string", "integer", "boolean", "number"]},
                    "default": {},
                    "description": {"type": "string", "maxLength": 200},
                },
            },
        },
        "events": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "produces": {**_LIST, "items": {"type": "string"}},
                "consumes": {**_LIST, "items": {"type": "string"}},
            },
        },
        "personal_data": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "enabled": {"type": "boolean"},
                "classes": {**_LIST, "items": {"type": "string", "maxLength": 64}},
                "erasure_participant": {"type": "boolean"},
            },
        },
        "capabilities_provided": {**_LIST, "items": {"type": "string", "maxLength": 96}},
        "migrations": {"type": "string", "pattern": r"^[a-z_]+$"},
        "i18n": {"type": "object"},
        "ui": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "nav": {**_LIST, "items": {"type": "object"}},
                "sections": {**_LIST, "items": {"type": "object"}},
                "pages": {**_LIST, "items": {"type": "object"}},
                "widgets": {**_LIST, "items": {"type": "object"}},
                "notification_categories": {**_LIST, "items": {"type": "object"}},
                "statistics": {**_LIST, "items": {"type": "object"}},
                "themes": {**_LIST, "items": {"type": "object"}},
            },
        },
    },
}


@dataclass(frozen=True, slots=True)
class Manifest:
    key: str
    name: str
    version: str
    raw: dict[str, Any] = field(compare=False)

    @property
    def scope(self) -> str:
        return str(self.raw.get("scope", "portal"))

    @property
    def maturity(self) -> str:
        return str(self.raw.get("maturity", "experimental"))

    @property
    def entry_point(self) -> str | None:
        value = self.raw.get("entry_point")
        return str(value) if value else None

    @property
    def requires_plugins(self) -> list[dict[str, str]]:
        return [dict(r) for r in self.raw.get("requires_plugins", [])]

    @property
    def requires_capabilities(self) -> list[dict[str, str]]:
        return [dict(r) for r in self.raw.get("requires_capabilities", [])]

    @property
    def extension_points(self) -> list[str]:
        return list(self.raw.get("extension_points", []))

    @property
    def owner(self) -> str:
        return f"plugin:{self.key}"

    def permission_keys(self) -> list[str]:
        return [f"plugin:{self.key}.{p['name']}" for p in self.raw.get("permissions", [])]

    def event_types(self) -> list[str]:
        return [f"plugin.{self.key}.{n}" for n in self.raw.get("events", {}).get("produces", [])]

    @property
    def personal_data(self) -> bool:
        return bool(self.raw.get("personal_data", {}).get("enabled", False))


class InvalidManifest(ValidationFailed):
    default_code = "plugin.invalid_manifest"
    default_title = "Invalid plugin manifest"


def _fail(problems: list[str]) -> InvalidManifest:
    return InvalidManifest("This plugin manifest is not valid.", extensions={"problems": problems[:20]})


def validate(raw: dict[str, Any]) -> Manifest:
    try:
        jsonschema.validate(raw, SCHEMA)
    except jsonschema.ValidationError as exc:
        path = "/".join(str(p) for p in exc.absolute_path)
        raise _fail([f"{path or 'manifest'}: {exc.message[:160]}"]) from exc
    problems: list[str] = []
    key = raw["key"]
    try:
        version = Version(raw["version"])
        if len(version.release) != 3:
            problems.append("version: use MAJOR.MINOR.PATCH")
    except InvalidVersion:
        problems.append("version: not a semantic version")
    ranges = [("requires_portal", raw.get("requires_portal"))]
    ranges += [
        (f"requires_capabilities/{r['name']}", r.get("range")) for r in raw.get("requires_capabilities", [])
    ]
    ranges += [(f"requires_plugins/{r['key']}", r.get("range")) for r in raw.get("requires_plugins", [])]
    for where, value in ranges:
        if value:
            try:
                SpecifierSet(value)
            except InvalidSpecifier:
                problems.append(f"{where}: invalid version range {value!r}")
    if any(r["key"] == key for r in raw.get("requires_plugins", [])):
        problems.append("requires_plugins: a plugin cannot depend on itself")
    for permission in raw.get("permissions", []):
        name = permission["name"]
        if permission.get("reserved"):
            problems.append(f"permissions/{name}: plugins never declare reserved (Admin-only) permissions")
        if not re.fullmatch(NAME, name):
            problems.append(f"permissions/{name}: permissions are namespaced plugin:{key}.<name>")
    events = raw.get("events", {})
    for name in events.get("produces", []):
        if not re.fullmatch(NAME, name):
            problems.append(f"events/produces/{name}: events are namespaced plugin.{key}.<name>")
    for name in events.get("consumes", []):
        if not re.fullmatch(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$", name):
            problems.append(f"events/consumes/{name}: not an event type")
    personal = raw.get("personal_data", {})
    if personal.get("enabled") and not personal.get("erasure_participant"):
        problems.append("personal_data: a plugin keeping personal data must provide an erasure participant")
    unknown = sorted(set(raw.get("extension_points", [])) - set(EXTENSION_POINTS))
    if unknown:
        problems.append(f"extension_points: unknown points {unknown} (plugins cannot define new ones)")
    for capability in raw.get("capabilities_provided", []):
        if not capability.startswith(f"plugin:{key}.") and not capability.startswith(f"plugin.{key}."):
            problems.append(
                f"capabilities_provided/{capability}: plugin capabilities are namespaced plugin.{key}.<name>"
            )
    if problems:
        raise _fail(problems)
    return Manifest(key, raw["name"], raw["version"], raw)


def parse_toml(text: str) -> Manifest:
    if len(text.encode()) > MAX_BYTES:
        raise _fail(["manifest: larger than 64 KB"])
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise _fail([f"manifest: {str(exc)[:160]}"]) from exc
    return validate(raw)
