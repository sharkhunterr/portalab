"""Replaying what a confined plugin registered (spec 030, R1) on spec 023's own context.

The plugin's process sent its registrations as data, its callables as references; they are applied here to
023's :class:`Context` — the same registries, guard, ledger and conflict rules as any plugin — after two
checks of Portalab's own: each registration needs a capability the Admin granted, and what it names (a
route and its label, a permission, an event) must be declared in the manifest the Admin reviewed.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY, ExportRecord
from portalab.modules.plugins.context.plugin_context import Context
from portalab.modules.plugins.manifest.schema import SLOTS, Manifest

# the capability each registration needs (None: nothing beyond the review itself)
NEEDS: dict[str, str | None] = {
    "route": "operations",
    "ai_tool": "operations",
    "page": "pages",
    "nav_entry": "pages",
    "nav_section": "pages",
    "widget": "pages",
    "statistics_pack": "pages",
    "calendar_source": "pages",
    "action": "search",
    "search_provider": "search",
    "consume": "events",
    "event_type": "events",
    "automation_action": "events",
    "notification_category": "notifications",
    "product_type": "product_types",
    "profile_section": "slots",
    "discovery_shelf": "slots",
    "slot": "slots",
    "permission": "permissions",
    "setting": "settings",
    "job": "jobs",
    "privacy": "privacy",
    "live_presence": "live",
    "theme": None,
    "i18n_catalog": None,
}
# never for a confined plugin: they would hand it what other code relies on
REFUSED = {"provide", "connector", "media_type"}
TYPES = {"str": str, "int": int, "bool": bool, "float": float, "string": str, "integer": int, "boolean": bool}


class PrivacyParticipant:
    """021's export and erasure, done by the plugin's own handlers (guarded like any of its calls)."""

    def __init__(self, ctx: Context, export: Any, erase: Any) -> None:
        self._key = ctx.key
        self._export = ctx.guard.wrap(ctx.key, "hook", export) if export is not None else None
        self._erase = ctx.guard.wrap(ctx.key, "hook", erase) if erase is not None else None

    async def export(self, user_id: Any) -> list[ExportRecord]:
        if self._export is None:
            return []
        data = await self._export(str(user_id))
        return [
            ExportRecord(
                category=f"plugin:{self._key}",
                data=dict(data) if isinstance(data, Mapping) else {"items": data},
            )
        ]

    async def erase(self, user_id: Any, mode: str = "final") -> None:
        if self._erase is not None:
            await self._erase(str(user_id))


@dataclass
class Registered:
    """What the runtime keeps beyond 023's registries for one confined plugin."""

    routes: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    privacy: dict[str, Any] = field(default_factory=dict)
    slots: list[dict[str, Any]] = field(default_factory=list)
    presence: dict[str, Any] = field(default_factory=dict)
    refused: list[tuple[str, str]] = field(default_factory=list)  # (registration, why)


def replay(
    ctx: Context,
    manifest: Manifest,
    calls: list[tuple[str, list[Any], dict[str, Any]]],
    granted: Mapping[str, Mapping[str, Any]],
    on_denied: Callable[[str, str], None],
    *,
    wrap_consumer: Callable[[Any], Any] = lambda handler: handler,
) -> Registered:
    out = Registered()
    declared_permissions = {str(p["name"]) for p in manifest.raw.get("permissions", [])}
    events = dict(manifest.capabilities.get("events") or {})
    produces = set(events.get("produces") or []) | set(manifest.raw.get("events", {}).get("produces", []))
    consumes = set(events.get("consumes") or []) | set(manifest.raw.get("events", {}).get("consumes", []))
    jobs = set(dict(manifest.capabilities.get("jobs") or {}).get("names") or [])
    slots = set(manifest.capabilities.get("slots") or [])
    topics = set(dict(manifest.capabilities.get("live") or {}).get("topics") or [])

    def refuse(method: str, ident: str, why: str, *, attempt: bool = False) -> None:
        ctx._conflict(method, ident, PermissionError(why))
        out.refused.append((f"{method}:{ident}", why))
        if attempt:
            on_denied(method, why)

    for method, args, kwargs in calls:
        ident = str(args[0]) if args else method
        if method in REFUSED:
            refuse(method, ident, "not available to confined plugins")
            continue
        if method not in NEEDS:
            refuse(method, ident, "unknown registration")
            continue
        need = NEEDS[method]
        if need is not None and need not in granted:
            refuse(method, ident, f"the {need} capability is not granted", attempt=True)
            continue
        try:
            if method == "route":
                verb, path, handler = str(args[0]).upper(), str(args[1]).strip("/"), args[2]
                label = manifest.route_label(verb, path)
                if label is None:
                    refuse(method, f"{verb} {path}", "the route is not declared in the manifest")
                    continue
                describe = kwargs.get("describe")
                if label == "committing" and describe is None:
                    refuse(method, f"{verb} {path}", "a committing route needs describe()")
                    continue
                ctx.route(verb, path, handler, permission=str(kwargs["permission"]))
                out.routes[(verb, path)] = {"exposure": label, "describe": describe}
            elif method == "permission":
                if str(args[0]) not in declared_permissions:
                    refuse(method, ident, "the permission is not declared in the manifest")
                    continue
                ctx.permission(str(args[0]), str(args[1]), **dict(kwargs))
            elif method == "setting":
                name, type_name, default, description = args
                ctx.setting(str(name), TYPES.get(str(type_name), str), default, str(description))
            elif method == "event_type":
                if str(args[0]) not in produces:
                    refuse(method, ident, "the event is not declared in the manifest")
                    continue
                ctx.event_type(str(args[0]), **dict(kwargs))
            elif method == "consume":
                name, types, handler = args
                undeclared = [t for t in types if t not in consumes]
                if undeclared:
                    refuse(method, str(name), f"consumes undeclared events {undeclared[:3]}")
                    continue
                ctx.consume(str(name), list(types), wrap_consumer(handler))
            elif method == "job":
                name, handler = args
                if str(name) not in jobs:
                    refuse(method, str(name), "the job is not declared in the manifest")
                    continue
                out.jobs[str(name)] = {"handler": handler, "every_minutes": kwargs.get("every_minutes")}
                ctx._ok("job", str(name))
            elif method == "privacy":
                export, erase = kwargs.get("export"), kwargs.get("erase")
                out.privacy = {"export": export, "erase": erase}
                participant = PrivacyParticipant(ctx, export, erase)
                if export is not None:
                    ctx.provide(EXPORT_CAPABILITY, participant)
                if erase is not None:
                    ctx.provide(ERASURE_CAPABILITY, participant)
            elif method == "product_type":
                product = args[0]
                declared = set(manifest.capabilities.get("product_types") or [])
                name = str(getattr(product, "key", "")).removeprefix(f"plugin:{ctx.key}.")
                if name not in declared:
                    refuse(method, str(getattr(product, "key", "?")), "the product type is not declared")
                    continue
                ctx.product_type(product)
            elif method == "slot":
                slot, key = str(args[0]), str(args[1])
                if slot not in SLOTS or slot not in slots:
                    refuse(method, f"{slot}:{key}", "the slot is not declared in the manifest")
                    continue
                out.slots.append({"slot": slot, "key": key, **dict(kwargs)})
                ctx._ok("slot", f"{slot}:{key}")
            elif method == "live_presence":
                topic, handler = args
                if str(topic) not in topics:
                    refuse(method, str(topic), "the live topic is not declared in the manifest")
                    continue
                out.presence[str(topic)] = handler
            else:
                getattr(ctx, method)(*args, **dict(kwargs))
        except Exception as error:  # an invalid registration never breaks the load (023's rule)
            refuse(method, ident, f"{type(error).__name__}: {str(error)[:160]}")
    if manifest.personal_data and not (out.privacy.get("export") and out.privacy.get("erase")):
        refuse("privacy", ctx.key, "a plugin keeping personal data must register privacy export and erase")
    return out
