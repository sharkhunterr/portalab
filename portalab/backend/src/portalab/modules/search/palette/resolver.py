"""Palette backend (T029, T032; R10-R12): ``GET /palette/resolve?q=&route=``.

* **action catalog** — 004 navigation commands plus registered context actions, each behind its own
  permission; context actions only on their page; ``sensitivity``/``confirmation_required`` passed through
  (the owning module enforces the ``ConfirmationService`` token and audits — the palette only launches);
* **object references** — ``portalab://kind/id`` or a resolver prefix (``#123``); answered only when the
  object exists **and** the principal may see it, else nothing (no existence oracle);
* **deterministic intents** — "go to …", "search …", known command aliases, per language; resolved
  instantly without AI;
* **assistant interpretation** — only for unresolved text, in parallel and time-boxed; returned as
  *suggestions* filtered to permitted destinations/commands, never executed.
"""

import asyncio
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.capabilities.navigation import NavigationContribution, NavigationRegistry, default_navigation
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import ASSISTANT, ActionDef, ObjectRef, SearchRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.search.coordinator.coordinator import SearchCoordinator
from portalab.modules.search.observability import log
from portalab.modules.search.providers.common import Labels

URI = re.compile(r"^portalab://([a-z][a-z0-9_:.-]{0,95})/([A-Za-z0-9_.:-]{1,128})$")
INTERPRET_TIMEOUT = 1.5

VERBS: Mapping[str, Mapping[str, str]] = {
    "en": {
        "go to": "navigate",
        "goto": "navigate",
        "open": "navigate",
        "show": "navigate",
        "search for": "search",
        "search": "search",
        "find": "search",
        "look for": "search",
    },
    "fr": {
        "aller a": "navigate",
        "aller sur": "navigate",
        "ouvrir": "navigate",
        "afficher": "navigate",
        "rechercher": "search",
        "chercher": "search",
        "trouver": "search",
    },
}


@dataclass(frozen=True, slots=True)
class PaletteEntry:
    id: str
    label: str
    kind: str  # "navigate" | "action"
    route: str | None = None
    action_id: str | None = None
    sensitivity: str = "normal"
    confirmation_required: bool = False
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Intent:
    type: str  # "navigate" | "search" | "command"
    target: str | None = None
    query: str | None = None
    route: str | None = None


@dataclass
class PaletteResolution:
    destinations: list[PaletteEntry] = field(default_factory=list)
    actions: list[PaletteEntry] = field(default_factory=list)
    object: ObjectRef | None = None
    intent: Intent | None = None
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    assistant: str = "off"  # off | ok | unavailable

    def as_dict(self) -> dict[str, Any]:
        return {
            "destinations": [asdict(e) for e in self.destinations],
            "actions": [asdict(e) for e in self.actions],
            "object": asdict(self.object) if self.object else None,
            "intent": asdict(self.intent) if self.intent else None,
            "suggestions": self.suggestions,
            "assistant": self.assistant,
        }


class PaletteResolver:
    def __init__(
        self,
        registry: SearchRegistry,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        coordinator: SearchCoordinator,
        navigation: NavigationRegistry = default_navigation,
    ) -> None:
        self.registry = registry
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.coordinator = coordinator
        self.navigation = navigation
        self.labels = Labels(capabilities)

    async def _held(self, principal: Principal, permissions: list[str]) -> set[str]:
        """Issue 404: the permissions held among ``permissions`` — one batch, not audited, when the engine
        offers it (what the palette shows, not what is done); else one check each."""
        visible = getattr(self.authorizer, "visible", None)
        if visible is not None:
            try:
                return set(await visible(principal, permissions))
            except Exception:
                return set()
        unique = sorted(set(permissions))
        allowed = await asyncio.gather(*(self._allowed(principal, p) for p in unique))
        return {p for p, ok in zip(unique, allowed, strict=True) if ok}

    async def _allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    # --- catalog --------------------------------------------------------------------------------------
    async def catalog(
        self, principal: Principal, ctx: LocaleContext, route: str | None
    ) -> tuple[list[PaletteEntry], list[PaletteEntry]]:
        contributions = [c for c in self.navigation.all() if c.kind in ("entry", "command")]
        actions: list[ActionDef] = [
            a
            for a in self.registry.actions()
            if a.context_route is None or (route or "").startswith(a.context_route)
        ]
        wanted = [c.required_permission for c in contributions] + [a.permission for a in actions]
        held = await self._held(principal, wanted)
        allowed_nav = [c.required_permission in held for c in contributions]
        allowed_act = [a.permission in held for a in actions]
        destinations: list[PaletteEntry] = []
        commands: list[PaletteEntry] = []
        for contribution, ok in zip(contributions, allowed_nav, strict=True):
            if ok:
                entry = self._from_nav(contribution, ctx)
                (destinations if contribution.kind == "entry" else commands).append(entry)
        for action, ok in zip(actions, allowed_act, strict=True):
            if ok:
                commands.append(
                    PaletteEntry(
                        id=action.id,
                        label=self.labels(action.label_key, ctx),
                        kind="action" if action.action_id else "navigate",
                        route=action.route,
                        action_id=action.action_id,
                        sensitivity=action.sensitivity,
                        confirmation_required=action.confirmation_required or action.sensitivity != "normal",
                        keywords=action.keywords,
                    )
                )
        return destinations, commands

    def _from_nav(self, c: NavigationContribution, ctx: LocaleContext) -> PaletteEntry:
        return PaletteEntry(
            id=c.key,
            label=self.labels(c.label_key, ctx),
            kind="action" if c.action_id else "navigate",
            route=c.route,
            action_id=c.action_id,
            sensitivity=c.sensitivity,
            confirmation_required=c.confirmation_required or c.sensitivity != "normal",
            keywords=c.keywords,
        )

    # --- objects -------------------------------------------------------------------------------------
    async def resolve_object(self, ref: str, principal: Principal) -> ObjectRef | None:
        ref = ref.strip()
        if match := URI.fullmatch(ref):
            kind, item_id = match.groups()
            for resolver in self.registry.resolvers():
                if resolver.kind == kind and await self._resolver_allowed(principal, kind):
                    return await self._safe_resolve(resolver, item_id, principal)
            providers = await self.coordinator.permitted(principal, [kind])
            if not providers:
                return None
            try:
                items = await asyncio.wait_for(providers[0].hydrate([item_id], principal), timeout=2)
            except Exception:
                return None
            return ObjectRef(kind, items[0].id, items[0].title, items[0].url_ref) if items else None
        for resolver in self.registry.resolvers():
            if any(ref.startswith(prefix) for prefix in resolver.prefixes) and await self._resolver_allowed(
                principal, resolver.kind
            ):
                found = await self._safe_resolve(resolver, ref, principal)
                if found is not None:
                    return found
        return None

    async def _resolver_allowed(self, principal: Principal, kind: str) -> bool:
        provider = self.registry.provider(kind)
        return provider is None or await self._allowed(principal, provider.required_permission)

    async def _safe_resolve(self, resolver: Any, ref: str, principal: Principal) -> ObjectRef | None:
        try:
            result = await asyncio.wait_for(resolver.resolve(ref, principal), timeout=2)
        except Exception:
            return None
        return result if isinstance(result, ObjectRef) else None

    # --- intents -------------------------------------------------------------------------------------
    def intent(
        self,
        text: str,
        ctx: LocaleContext,
        destinations: Sequence[PaletteEntry],
        commands: Sequence[PaletteEntry],
    ) -> Intent | None:
        folded = normalize_for_search(" ".join(text.split()), ctx.language)
        if not folded:
            return None
        verbs = {**VERBS["en"], **VERBS.get(ctx.language.split("-")[0], {})}
        for verb in sorted(verbs, key=len, reverse=True):
            if folded == verb or folded.startswith(verb + " "):
                rest = folded[len(verb) :].strip()
                if verbs[verb] == "search":
                    return Intent("search", query=text.split(None, len(verb.split()))[-1] if rest else "")
                target = self._best(rest, destinations)
                return Intent("navigate", target=target.id, route=target.route) if target else None
        for command in commands:  # exact alias / label of a permitted command
            names = {normalize_for_search(n, ctx.language) for n in (command.label, *command.keywords)}
            if folded in names:
                return Intent("command", target=command.id, route=command.route)
        target = self._best(folded, destinations, exact=True)
        return Intent("navigate", target=target.id, route=target.route) if target else None

    @staticmethod
    def _best(text: str, entries: Sequence[PaletteEntry], *, exact: bool = False) -> PaletteEntry | None:
        if not text:
            return None
        best: tuple[int, PaletteEntry] | None = None
        for entry in entries:
            names = [normalize_for_search(n) for n in (entry.label, *entry.keywords)]
            for name in names:
                score = (
                    3
                    if name == text
                    else (0 if exact else 2 if name.startswith(text) else 1 if text in name else 0)
                )
                if score and (best is None or score > best[0]):
                    best = (score, entry)
        return best[1] if best else None

    # --- entry point ---------------------------------------------------------------------------------
    async def resolve(
        self, q: str, principal: Principal, ctx: LocaleContext, route: str | None
    ) -> PaletteResolution:
        destinations, commands = await self.catalog(principal, ctx, route)
        out = PaletteResolution(destinations=destinations, actions=commands)
        text = " ".join(q.split())[:256]
        if not text:
            return out
        out.object = await self.resolve_object(text, principal)
        if out.object is not None:
            return out
        out.intent = self.intent(text, ctx, destinations, commands)
        if out.intent is None:
            out.suggestions, out.assistant = await self.interpret(
                text, principal, route, destinations, commands
            )
        return out

    async def interpret(
        self,
        text: str,
        principal: Principal,
        route: str | None,
        destinations: Sequence[PaletteEntry],
        commands: Sequence[PaletteEntry],
    ) -> tuple[list[dict[str, Any]], str]:
        providers = self.capabilities.system_providers(ASSISTANT)
        if not providers:
            return [], "unavailable"
        try:
            raw = await asyncio.wait_for(
                providers[0].provider.interpret(text, principal, route), INTERPRET_TIMEOUT
            )
        except Exception:
            log.warning("palette interpretation unavailable")
            return [], "unavailable"
        routes = {d.route for d in destinations if d.route} | {c.route for c in commands if c.route}
        command_ids = {c.id for c in commands}
        suggestions = []
        for suggestion in list(raw)[:5]:
            if suggestion.route is not None and suggestion.route not in routes:
                continue  # never suggest a destination the user cannot open
            if suggestion.command_key is not None and suggestion.command_key not in command_ids:
                continue
            suggestions.append({**asdict(suggestion), "suggested_by": "assistant"})
        return suggestions, "ok"
