"""027 T031 — ``GET /me/navigation`` sections: an administrator sees at most 9 top-level sections (8 for a
user), Administration grouped by topics, personal destinations in ``personal``, empty sections absent,
single-entry sections direct, unknown sections placed (never dropped) with a diagnostic, the 004 ``groups``
alias kept, and the degraded view still carries empty sections."""

from typing import Any

from portalab.core.authz_port import Principal
from tests.authz_fixtures import insert_user, make_admin, user
from tests.integration.shell.conftest import ShellHarness


def keys(view: dict[str, Any]) -> list[str]:
    return [s["key"] for s in view["sections"]]


def entries(section: dict[str, Any]) -> set[str]:
    return {e["key"] for e in section["entries"]} | {
        e["key"] for t in section["topics"] for e in t["entries"]
    }


async def test_sections_for_users_and_admins(sh: ShellHarness) -> None:
    plain = user(await insert_user(sh.full.database))
    admin_id = await insert_user(sh.full.database)
    await make_admin(sh.full, admin_id)
    view = await sh.module.assembler.build(plain)
    admin = await sh.module.assembler.build(user(admin_id))

    # 032: « My household » is a section of its own — 027's nine, plus one
    assert len(view["sections"]) <= 9 and len(admin["sections"]) <= 10
    assert "admin" not in keys(view) and "admin" in keys(admin)
    assert keys(admin)[-1] == "admin"  # the Administration area closes the navigation
    by_key = {s["key"]: s for s in admin["sections"]}
    home = by_key["home"]
    assert home["direct"] is True and [e["route"] for e in home["entries"]] == ["/"]
    assert "support.tickets" in entries(by_key["support"])
    topics = {t["key"]: {e["key"] for e in t["entries"]} for t in by_key["admin"]["topics"]}
    # 027 hubs: Administration in a few hubs, each opening on its first page
    # #4: « media » (requests to decide, quotas, identity, history) right after the services
    order = list(topics)
    assert order.index("media") == order.index("services") + 1
    assert {"media.requests_admin", "media.quotas", "media.admin", "media.sources"} <= topics["media"]
    # the hubs in their order — all of them: the harness runs on the production permission catalog (#139)
    expected = [
        "pilot",
        "members",
        "services",  # admin reorganisation (trial): « Operations » — services, incidents, maintenance
        "support",
        "communication",
        "engagement",
        "shop",
        "appearance",  # the theme studio, the members' dashboard, the site's identity
        "automations",  # 027: a hub of its own
        "extensions",  # 028: visual packs, widgets, plugins, modules
        "ai",  # issue 176: the assistant's dashboard, model, identity and tools
        "system",
    ]
    assert [key for key in order if key != "media"] == expected
    assert {"ai.admin", "ai.model", "ai.identity", "ai.tools"} <= topics["ai"]
    automations = {"automations.admin", "automations.new", "automations.history", "automations.templates"}
    assert automations <= topics["automations"]  # the whole hub, whatever ran before in the process
    assert {"authz.roles", "identity.members"} <= topics["members"] and "authz.audit" in topics["pilot"]
    assert "support.queue" in topics["support"] and "wiki.admin" in topics["communication"]
    assert {"support.incident_console", "health.maintenance", "health.alert_rules"} <= topics["services"]
    assert "news.newsletters" in topics["communication"]
    assert "plugins.modules" in topics["extensions"]  # 028: what extends Portalab, one hub
    hubs = {t["key"]: t for t in by_key["admin"]["topics"]}
    assert hubs["pilot"]["route"] == "/admin" and hubs["pilot"]["icon"] == "gauge"
    assert not by_key["admin"]["entries"]  # every built-in admin entry has a topic

    personal = {e["key"] for e in view["personal"]}
    # #298: « Moi » — what is mine; the settings' pages are listed by « My settings », not one by one
    assert {"shell.settings", "gamification.progression"} <= personal
    assert "community.quests" in {e["key"] for e in by_key["games"]["entries"]}  # #310: among the games
    stats = {e["key"] for e in by_key["stats"]["entries"]}  # #298: mine, my requests', the community's
    assert {"media.insights", "media.requests_stats", "statistics.page"} <= stats
    assert not {"identity.account", "ui.appearance", "i18n.language", "privacy.center"} & personal
    commands = {c["key"] for c in view["commands"]}
    assert {"identity.account", "ui.appearance", "search.page"} <= commands
    assert not any(e.startswith("identity.") for s in view["sections"] for e in entries(s))
    assert "groups" in view and any(g["key"] == "me" for g in view["groups"])  # 004 alias kept

    every = {e for s in admin["sections"] for e in entries(s)} | {e["key"] for e in admin["personal"]}
    legacy = {e["key"] for g in admin["groups"] for e in g["entries"]}
    assert legacy == every  # nothing reachable before became unreachable


async def test_unknown_sections_are_placed_and_reported(sh: ShellHarness) -> None:
    for key, group in (("radio.player", "nope"), ("media.radio", "nope"), ("legacy.page", "main")):
        sh.registry.register(
            {
                "key": key,
                "owner": f"module:{key.split('.')[0]}",
                "kind": "entry",
                "label_key": "nav.x",
                "route": f"/{key.replace('.', '/')}",
                "group": group,
                "required_permission": "users.self.manage",
            }
        )
    view = await sh.module.assembler.build(user(await insert_user(sh.full.database)))
    placed = {e: s["key"] for s in view["sections"] for e in entries(s)}
    assert placed["radio.player"] == "more" and placed["legacy.page"] == "more"
    assert placed["media.radio"] == "media"  # owner default section
    await sh.module.flush_diagnostics()
    details = [e for e in await sh.module.isolator.errors() if e["reason"] == "runtime"]
    assert sorted(e["key"] for e in details) == ["media.radio", "radio.player"]  # legacy "main" is silent


async def test_degraded_view_has_empty_sections(sh: ShellHarness) -> None:
    class Broken:
        async def is_allowed(self, principal: Principal, permission: str, resource: object = None) -> bool:
            raise RuntimeError("authz down")

    sh.module.assembler.authorizer = Broken()  # type: ignore[assignment]
    view = await sh.module.assembler.build(user(await insert_user(sh.full.database)))
    assert view["degraded"] is True and view["sections"] == [] and view["personal"] == []


async def test_my_household_only_for_a_household(sh: ShellHarness) -> None:
    """Issue 445: « My household » shows to a member in a household only (a profile, or a master who made
    one); without a household service it shows as before."""
    from portalab.capabilities.household import CAPABILITY as HOUSEHOLD

    plain = user(await insert_user(sh.full.database))
    assert "household" in keys(await sh.module.assembler.build(plain))

    class Household:
        made = False

        async def exists(self, member: Any) -> bool:
            return self.made

        async def owner_of(self, member: Any) -> None:
            return None

        async def restrictions_of(self, member: Any) -> None:
            return None

        async def granted(self, member: Any, kind: str, ref: str) -> bool:
            return False

        async def grants(self, member: Any, kind: str) -> frozenset[str]:
            return frozenset()

        async def hidden(self) -> frozenset[Any]:
            return frozenset()

        async def anonymous(self) -> frozenset[Any]:
            return frozenset()

        async def profiles(self) -> frozenset[Any]:
            return frozenset()

        async def profiles_of(self, owner: Any) -> frozenset[Any]:
            return frozenset()

        async def economy_of(self, member: Any) -> str:
            return "pot"

    household = Household()
    sh.full.identity.capabilities.provide(HOUSEHOLD, household, instance_ref="test", owner="module:household")
    assert "household" not in keys(await sh.module.assembler.build(plain))
    household.made = True
    assert "household" in keys(await sh.module.assembler.build(plain))
