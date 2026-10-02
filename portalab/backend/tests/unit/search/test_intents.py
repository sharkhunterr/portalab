"""008 T031 — deterministic intents (navigate / search / known commands with aliases, per language)
resolve instantly without AI; unresolved text yields assistant *suggestions* only, filtered to permitted
destinations; an assistant outage leaves the deterministic path unaffected; object references reveal
nothing unless permitted."""

from collections.abc import Sequence

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.navigation import NavigationContribution, NavigationRegistry
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import ASSISTANT, SPECS, IntentSuggestion, SearchRegistry
from portalab.core.authz_port import Principal
from portalab.modules.search.coordinator.coordinator import SearchCoordinator
from portalab.modules.search.palette.resolver import PaletteResolver
from portalab.modules.search.settings import SearchConfig
from tests.unit.search.fakes import FakeAuthorizer, FakeProvider, FakeResolver

ME = Principal(user_id=None)


def nav() -> NavigationRegistry:
    registry = NavigationRegistry()
    for raw in (
        {
            "key": "health.services",
            "owner": "module:health",
            "kind": "entry",
            "label_key": "Services",
            "route": "/services",
            "required_permission": "services.read",
            "keywords": ("status",),
        },
        {
            "key": "admin.audit",
            "owner": "module:admin",
            "kind": "entry",
            "label_key": "Audit",
            "route": "/admin/audit",
            "required_permission": "audit.read",
        },
        {
            "key": "identity.delete",
            "owner": "module:identity",
            "kind": "command",
            "label_key": "Delete my account",
            "route": "/account/delete",
            "required_permission": "users.self.manage",
            "sensitivity": "sensitive",
            "keywords": ("close account",),
        },
    ):
        registry.register(NavigationContribution(**raw))  # type: ignore[arg-type]
    return registry


class Assistant:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def interpret(
        self, text: str, principal: Principal, page: str | None
    ) -> Sequence[IntentSuggestion]:
        if self.fail:
            raise RuntimeError("down")
        return [
            IntentSuggestion("Audit", route="/admin/audit"),
            IntentSuggestion("Services", route="/services"),
        ]

    def stream(self, *args: object) -> object:  # pragma: no cover - not used here
        raise NotImplementedError


def resolver(assistant: Assistant | None = None) -> PaletteResolver:
    capabilities = CapabilityRegistry()
    for spec in SPECS:
        capabilities.declare(spec)
    if assistant is not None:
        capabilities.provide(ASSISTANT, assistant, instance_ref="ai", owner="module:ai")
    registry = SearchRegistry()
    registry.register(FakeProvider("tickets", permission="tickets.read"), owner="module:support")
    registry.register_resolver(FakeResolver("tickets", {"123": "Printer"}), owner="module:support")
    authorizer = FakeAuthorizer({"search.use", "services.read", "users.self.manage"})
    coordinator = SearchCoordinator(registry, authorizer, SearchConfig)
    return PaletteResolver(registry, authorizer, capabilities, coordinator, navigation=nav())


async def test_catalog_is_permission_filtered() -> None:
    out = await resolver().resolve("", ME, LocaleContext(), "/")
    assert [d.id for d in out.destinations] == ["health.services"]  # no audit
    assert [(a.id, a.confirmation_required) for a in out.actions] == [("identity.delete", True)]


async def test_deterministic_intents() -> None:
    r = resolver(Assistant(fail=True))
    go = await r.resolve("go to services", ME, LocaleContext(), None)
    assert go.intent is not None and go.intent.route == "/services" and go.assistant == "off"
    fr = await r.resolve("rechercher factures 2026", ME, LocaleContext(language="fr"), None)
    assert fr.intent is not None and fr.intent.type == "search" and fr.intent.query == "factures 2026"
    alias = await r.resolve("close account", ME, LocaleContext(), None)
    assert (
        alias.intent is not None
        and alias.intent.type == "command"
        and alias.intent.target == "identity.delete"
    )
    hidden = await r.resolve("go to audit", ME, LocaleContext(), None)
    assert hidden.intent is None  # not permitted: no destination resolved


async def test_ai_suggestions_are_filtered_and_optional() -> None:
    out = await resolver(Assistant()).resolve("where is the thing about uptime", ME, LocaleContext(), None)
    assert out.intent is None and out.assistant == "ok"
    assert [s["route"] for s in out.suggestions] == ["/services"]
    assert all(s["suggested_by"] == "assistant" for s in out.suggestions)
    down = await resolver(Assistant(fail=True)).resolve("anything vague", ME, LocaleContext(), None)
    assert down.suggestions == [] and down.assistant == "unavailable" and down.destinations


async def test_object_references_reveal_nothing_unless_permitted() -> None:
    r = resolver()
    assert (await r.resolve("#123", ME, LocaleContext(), None)).object is None  # tickets.read missing
    r.authorizer.allowed.add("tickets.read")  # type: ignore[attr-defined]
    found = await r.resolve("#123", ME, LocaleContext(), None)
    assert found.object is not None and found.object.route == "/tickets/123"
    assert (await r.resolve("#999", ME, LocaleContext(), None)).object is None
    uri = await r.resolve("portalab://tickets/1", ME, LocaleContext(), None)
    assert uri.object is None  # the resolver does not know 1: nothing revealed
