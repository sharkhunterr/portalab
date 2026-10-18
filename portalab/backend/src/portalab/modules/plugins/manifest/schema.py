"""Plugin manifest (T008; R5): ``plugin.toml`` validated by a JSON Schema, then by semantic rules —
semantic version and version ranges, namespaced permissions (``plugin:<key>.<name>``, never reserved) and
events (``plugin.<key>.<name>``), personal data only with an erasure participant, only the official
extension points (plugins cannot define new ones), bounded sizes.

Version 2 (spec 030, contracts/manifest-v2.md) adds the ``runtime`` (``confined`` code runs in a process of
its own; version 1 code runs in Portalab's, ``in_process``), the closed list of ``[capabilities]`` the Admin
grants at review, the exposure label of each route, and secret settings Portalab keeps and injects."""

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
RUNTIMES = ("declarative", "confined", "in_process")
# spec 030 (FR-005): the closed list of what a confined plugin may be granted
CAPABILITIES = (
    "storage", "operations", "permissions", "pages", "slots", "live", "events", "jobs", "notifications",
    "search", "moderation", "privacy", "product_types", "settings", "network", "portal_data", "visual_types",
)  # fmt: skip
SLOTS = (
    "nav", "page", "header.action", "corner", "home.section", "media.actions", "media.panel", "person.panel",
    "profile.section",
    "player.overlay", "player.button", "settings.member", "settings.admin", "dashboard.widget",
    "search.kind", "notification.kind",
)  # fmt: skip
EXPOSURES = ("read", "action", "committing")
# 030: the shop's departments a plugin may put a shelf of its own in (the shop's own layout, spec 027)
SHOP_DEPARTMENTS = ("themes", "profile", "effects", "features", "packs")
HOST = r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$"
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
VIEW = r"^[a-z0-9_\-]{1,40}(/[a-z0-9_\-]{1,40}){0,3}\.m?js$"
_SIZE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "width": {"type": "integer", "minimum": 24, "maximum": 480},
        "height": {"type": "integer", "minimum": 24, "maximum": 720},
    },
}
_NAMES = {**_LIST, "items": {"type": "string", "pattern": r"^[a-z][a-z0-9_]{0,47}$"}}
_CAPABILITIES: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "storage": {
            "oneOf": [
                {"type": "boolean"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"quota_mb": {"type": "integer", "minimum": 1, "maximum": 10_000}},
                },
            ]
        },
        "operations": {"type": "boolean"},
        "permissions": {"oneOf": [{"type": "boolean"}, _NAMES]},
        "pages": {"type": "boolean"},
        "slots": {**_LIST, "items": {"enum": list(SLOTS)}},
        "live": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"topics": _NAMES},
        },
        "events": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "produces": _NAMES,
                "consumes": {**_LIST, "items": {"type": "string", "maxLength": 96}},
            },
        },
        "jobs": {"type": "object", "additionalProperties": False, "properties": {"names": _NAMES}},
        "notifications": {"type": "boolean"},
        "search": {"type": "boolean"},
        "moderation": {"type": "boolean"},
        "privacy": {"type": "boolean"},
        "product_types": _NAMES,
        # kinds of visuals it draws (its message bubbles…): packs bring looks of them, the shop sells them
        "visual_types": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "label_key"],
                "properties": {
                    "key": {"type": "string", "pattern": NAME},
                    "label_key": {"type": "string", "maxLength": 120},
                    "render": {"type": "array", "items": {"enum": ["css", "glsl"]}, "maxItems": 2},
                    "icon": {"type": "string", "pattern": r"^[a-z0-9-]{1,40}$"},
                },
            },
        },
        "settings": {"type": "boolean"},
        "network": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "hosts": {
                    **_LIST,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["host"],
                        "properties": {
                            "host": {"type": "string", "maxLength": 253},
                            "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                            "scheme": {"enum": ["https", "http"]},
                            "private": {"type": "boolean"},
                        },
                    },
                }
            },
        },
        "portal_data": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "operations": {**_LIST, "items": {"type": "string", "maxLength": 96}},
                "job_permissions": {**_LIST, "items": {"type": "string", "maxLength": 96}},
            },
        },
    },
}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["key", "name", "version"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [1, 2]},
        "runtime": {"enum": list(RUNTIMES)},
        "capabilities": _CAPABILITIES,
        # 030: what a plugin adds to Portalab's screens (drawn by Portalab), and the surfaces it opens
        "slots": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["slot", "key", "label_key", "permission"],
                "properties": {
                    "slot": {"enum": list(SLOTS)},
                    "key": {"type": "string", "pattern": NAME},
                    "label_key": {"type": "string", "maxLength": 120},
                    "icon": {"type": "string", "pattern": r"^[a-z0-9-]{1,40}$"},
                    "permission": {"type": "string", "maxLength": 96},
                    "opens": {"type": "string", "pattern": NAME},
                    "link": {"type": "string", "maxLength": 200},
                    "badge": {"type": "string", "pattern": r"^[a-z0-9_\-/]{1,120}$"},
                    "live": {"type": "string", "pattern": NAME},
                    # its own look: a view of the plugin drawn in a sandbox at the slot (a launcher…)
                    "view": {"type": "string", "pattern": VIEW},
                    "size": _SIZE,
                    "position": {"enum": ["bottom-right", "bottom-left"]},
                },
            },
        },
        "surfaces": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "kind", "title_key", "permission"],
                "properties": {
                    "key": {"type": "string", "pattern": NAME},
                    "kind": {"enum": ["modal", "drawer", "drawer-left", "panel"]},
                    "view": {"type": "string", "pattern": VIEW},
                    "position": {"enum": ["bottom-right", "bottom-left"]},
                    "title_key": {"type": "string", "maxLength": 120},
                    "permission": {"type": "string", "maxLength": 96},
                    "blocks": {**_LIST, "items": {"type": "object"}},
                },
            },
        },
        # where the shop shows the products of its own kinds: a department of Portalab's shop, a shelf of
        # its own there (named by the plugin), the kinds of products it holds
        "shelves": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "department", "label_key", "types"],
                "properties": {
                    "key": {"type": "string", "pattern": NAME},
                    "department": {"enum": list(SHOP_DEPARTMENTS)},
                    "label_key": {"type": "string", "maxLength": 120},
                    "icon": {"type": "string", "pattern": r"^[a-z0-9-]{1,40}$"},
                    "types": {**_NAMES, "minItems": 1},
                },
            },
        },
        "routes": {
            **_LIST,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "method", "permission", "exposure"],
                "properties": {
                    "path": {"type": "string", "pattern": r"^[a-z0-9_\-/{}]{1,120}$"},
                    "method": {"enum": ["GET", "POST"]},
                    "permission": {"type": "string", "maxLength": 96},
                    "exposure": {"enum": list(EXPOSURES)},
                },
            },
        },
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
                    "secret": {"type": "boolean"},
                    "inject": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["host"],
                        "properties": {
                            "host": {"type": "string", "maxLength": 253},
                            "header": {"type": "string", "pattern": r"^[A-Za-z0-9-]{1,64}$"},
                            "query": {"type": "string", "pattern": r"^[A-Za-z0-9_]{1,64}$"},
                        },
                    },
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

    # --- spec 030 ----------------------------------------------------------------------------------------
    @property
    def schema_version(self) -> int:
        return int(self.raw.get("schema_version", 1))

    @property
    def runtime(self) -> str:
        if "runtime" in self.raw:
            return str(self.raw["runtime"])
        if self.schema_version >= 2:
            return "confined" if self.entry_point else "declarative"
        return "in_process" if self.entry_point else "declarative"

    @property
    def capabilities(self) -> dict[str, Any]:
        """What the version asks the Admin to grant (only the truthy entries count)."""
        return {
            k: v for k, v in dict(self.raw.get("capabilities", {})).items() if v not in (False, None, [], {})
        }

    def requested_capabilities(self) -> list[str]:
        asked = set(self.capabilities)
        if self.raw.get("permissions"):
            asked.add("permissions")  # declaring permissions is asking for them
        if self.secret_settings() or self.raw.get("settings"):
            asked.add("settings")
        return sorted(asked)

    @property
    def routes(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.raw.get("routes", [])]

    def route_label(self, method: str, path: str) -> str | None:
        for route in self.routes:
            if route["method"] == method.upper() and route["path"].strip("/") == path.strip("/"):
                return str(route["exposure"])
        return None

    @property
    def visual_types(self) -> list[dict[str, Any]]:
        return [dict(v) for v in self.capabilities.get("visual_types") or []]

    @property
    def shelves(self) -> list[dict[str, Any]]:
        """Where the shop shows its kinds of products (``types`` are the full ``plugin:<key>.<type>``)."""
        return [
            {**dict(x), "types": [f"plugin:{self.key}.{t}" for t in x["types"]]}
            for x in self.raw.get("shelves", [])
        ]

    @property
    def slots(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self.raw.get("slots", [])]

    def surface(self, key: str) -> dict[str, Any] | None:
        return next((dict(x) for x in self.raw.get("surfaces", []) if x["key"] == key), None)

    @property
    def network_hosts(self) -> list[dict[str, Any]]:
        hosts = dict(self.capabilities.get("network") or {}).get("hosts") or []
        return [
            {
                "host": str(h["host"]).lower(),
                "port": int(h.get("port") or (443 if h.get("scheme", "https") == "https" else 80)),
                "scheme": str(h.get("scheme", "https")),
                "private": bool(h.get("private", False)),
            }
            for h in hosts
        ]

    def secret_settings(self) -> list[dict[str, Any]]:
        return [dict(s) for s in self.raw.get("settings", []) if s.get("secret")]

    @property
    def portal_operations(self) -> list[str]:
        return list(dict(self.capabilities.get("portal_data") or {}).get("operations") or [])

    @property
    def job_permissions(self) -> list[str]:
        return list(dict(self.capabilities.get("portal_data") or {}).get("job_permissions") or [])


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
    version_2 = int(raw.get("schema_version", 1)) >= 2
    if version_2:
        problems += _problems_v2(raw)
    elif any(k in raw for k in ("runtime", "capabilities", "routes", "slots", "surfaces", "shelves")):
        problems.append("runtime, capabilities, routes, slots, surfaces and shelves need schema_version = 2")
    if version_2 and personal.get("enabled") and not dict(raw.get("capabilities", {})).get("privacy"):
        problems.append("personal_data: a plugin keeping personal data must ask for the privacy capability")
    elif personal.get("enabled") and not personal.get("erasure_participant") and not version_2:
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


def _problems_v2(raw: dict[str, Any]) -> list[str]:
    import ipaddress

    problems: list[str] = []
    runtime = raw.get("runtime", "confined" if raw.get("entry_point") else "declarative")
    if runtime == "in_process":
        problems.append("runtime: a version 2 plugin's code always runs confined")
    if runtime == "confined" and not raw.get("entry_point"):
        problems.append("runtime: confined code needs an entry_point")
    if runtime == "declarative" and raw.get("entry_point"):
        problems.append("runtime: a declarative plugin has no entry_point")
    capabilities = dict(raw.get("capabilities", {}))
    hosts: set[str] = set()
    for item in dict(capabilities.get("network") or {}).get("hosts") or []:
        host = str(item["host"]).lower()
        hosts.add(host)
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "*" in host or not re.fullmatch(HOST, host):
                problems.append(f"capabilities/network/{host}: a host name, never a wildcard")
            continue
        if not address.is_global and not item.get("private"):
            problems.append(f"capabilities/network/{host}: a private address must say private = true")
    for setting in raw.get("settings", []):
        if setting.get("secret"):
            inject = setting.get("inject")
            if not inject or not (inject.get("header") or inject.get("query")):
                problems.append(f"settings/{setting['name']}: a secret is injected by Portalab (inject)")
            elif str(inject["host"]).lower() not in hosts:
                problems.append(
                    f"settings/{setting['name']}: injected toward a host the plugin does not list"
                )
        elif setting.get("inject"):
            problems.append(f"settings/{setting['name']}: only secrets are injected")
    declared = {str(p["name"]) for p in raw.get("permissions", [])}
    asked = dict(capabilities).get("permissions")
    for name in asked if isinstance(asked, list) else []:
        if name not in declared:
            problems.append(f"capabilities/permissions/{name}: not declared in permissions")
    if raw.get("routes") and not capabilities.get("operations"):
        problems.append("routes: declaring routes needs the operations capability")
    for route in raw.get("routes", []):
        permission = str(route["permission"])
        own = permission.removeprefix(f"plugin:{raw['key']}.")
        if permission.startswith("plugin:") and (own == permission or own not in declared):
            problems.append(f"routes/{route['path']}: permission {permission} is not one of this plugin's")
        elif not permission.startswith("plugin:") and "." not in permission and permission not in declared:
            problems.append(f"routes/{route['path']}: permission {permission} is not declared")
    surfaces = {str(x["key"]) for x in raw.get("surfaces", [])}
    asked_slots = set(capabilities.get("slots") or [])
    gets = {r["path"].strip("/") for r in raw.get("routes", []) if r["method"] == "GET"}
    topics = set(dict(capabilities.get("live") or {}).get("topics") or [])
    for item in raw.get("slots", []):
        where = f"slots/{item['slot']}:{item['key']}"
        if item["slot"] not in asked_slots:
            problems.append(f"{where}: the slot is not asked in capabilities.slots")
        if item.get("opens") and item["opens"] not in surfaces:
            problems.append(f"{where}: opens a surface that is not declared")
        if item.get("link") and not str(item["link"]).startswith(f"/plugins/{raw['key']}/"):
            problems.append(f"{where}: a link goes to one of the plugin's own pages")
        if item.get("badge") and item["badge"].strip("/") not in gets:
            problems.append(f"{where}: its badge reads a route that is not declared")
        if item.get("live") and item["live"] not in topics:
            problems.append(f"{where}: its live topic is not declared")
        if not (item.get("opens") or item.get("link") or item.get("view")):
            problems.append(f"{where}: a slot opens a surface, links to a page or shows its view")
        if item["slot"] == "corner" and not item.get("position"):
            problems.append(f"{where}: a corner slot says which corner (position)")
    for item in raw.get("surfaces", []):
        if not item.get("view") and not item.get("blocks"):
            problems.append(f"surfaces/{item['key']}: a surface holds blocks or the plugin's view")
    if raw.get("slots") and not raw.get("capabilities", {}).get("slots"):
        problems.append("slots: declaring slots needs the slots capability")
    sold = set(capabilities.get("product_types") or [])
    shelved: set[str] = set()
    for item in raw.get("shelves", []):
        for kind in item["types"]:
            if kind not in sold:
                problems.append(f"shelves/{item['key']}: {kind} is not one of its product_types")
            if kind in shelved:
                problems.append(f"shelves/{item['key']}: {kind} is already on another shelf")
            shelved.add(kind)
    if len({x["key"] for x in raw.get("shelves", [])}) != len(raw.get("shelves", [])):
        problems.append("shelves: the same shelf twice")
    keys = [(r["method"], r["path"].strip("/")) for r in raw.get("routes", [])]
    if len(keys) != len(set(keys)):
        problems.append("routes: the same route twice")
    return problems


def parse_toml(text: str) -> Manifest:
    if len(text.encode()) > MAX_BYTES:
        raise _fail(["manifest: larger than 64 KB"])
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise _fail([f"manifest: {str(exc)[:160]}"]) from exc
    return validate(raw)
