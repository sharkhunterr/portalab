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

    assert len(view["sections"]) <= 8 and len(admin["sections"]) <= 9
    assert "admin" not in keys(view) and "admin" in keys(admin)
    assert keys(admin)[-1] == "admin"  # the Administration area closes the navigation
    by_key = {s["key"]: s for s in admin["sections"]}
    home = by_key["home"]
    assert home["direct"] is True and [e["route"] for e in home["entries"]] == ["/"]
    assert "support.tickets" in entries(by_key["support"])
    topics = {t["key"]: {e["key"] for e in t["entries"]} for t in by_key["admin"]["topics"]}
    # 027 hubs: Administration in a few hubs, each opening on its first page
    # #4: « media » (requests to decide, quotas, identity, history) shows when the media module is there
    order = list(topics)
    if "media" in order:
        assert order.index("media") == order.index("services") + 1
        assert {"media.requests_admin", "media.quotas", "media.admin", "media.sources"} <= topics["media"]
    assert [key for key in order if key != "media"] == [
        "pilot",
        "members",
        "services",
        "support",
        "communication",
        "engagement",
        "shop",
        "automations",  # 027: a hub of its own
        "extensions",  # 028: visual packs, widgets, plugins, modules
        "system",
    ]
    assert {"automations.admin", "automations.history"} <= topics["automations"]
    assert {"authz.roles", "identity.members"} <= topics["members"] and "authz.audit" in topics["pilot"]
    assert {"support.queue", "wiki.admin"} <= topics["support"]
    assert "plugins.modules" in topics["extensions"]  # 028: what extends Portalab, one hub
    hubs = {t["key"]: t for t in by_key["admin"]["topics"]}
    assert hubs["pilot"]["route"] == "/admin" and hubs["pilot"]["icon"] == "gauge"
    assert not by_key["admin"]["entries"]  # every built-in admin entry has a topic

    personal = {e["key"] for e in view["personal"]}
    assert {"identity.account", "ui.appearance", "i18n.language", "privacy.center"} <= personal
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
