"""004 T009/T011 — per-entry permission filtering (granted, denied, default deny), disabled modules hide
their entries, hidden entries never leak, failing contributions are isolated, authz failure ⇒ minimal nav."""

from typing import Any

from sqlalchemy import text

from portalab.core.authz_port import Principal
from portalab.modules.authz.grants.service import GrantSpec
from portalab.modules.authz.models import BASE_ROLE_IDS
from tests.authz_fixtures import SYSTEM_ACTOR, insert_user, make_admin, user
from tests.integration.shell.conftest import ShellHarness


def labels(view: dict[str, Any]) -> set[str]:
    return {e["key"] for g in view["groups"] for e in g["entries"]}


async def test_rights_aware_navigation(sh: ShellHarness) -> None:
    plain = user(await insert_user(sh.full.database))
    admin_id = await insert_user(sh.full.database)
    await make_admin(sh.full, admin_id)
    plain_view = await sh.module.assembler.build(plain)
    admin_view = await sh.module.assembler.build(user(admin_id))
    assert {"shell.home", "identity.account", "health.services"} <= labels(plain_view)
    assert not any(
        key.startswith(("administration.", "authz.", "observability.")) for key in labels(plain_view)
    )
    assert {"administration.control_center", "authz.audit", "authz.roles"} <= labels(admin_view)
    assert "administration" not in str(plain_view)  # hidden entries never leak names
    assert (
        "health.services" in [r["key"] for r in admin_view["related"]["/services"]]
        or admin_view["related"]["/services"]
    )
    assert "/services" not in plain_view["related"]  # related link needs services.manage

    # grant audit.read to the base user role: the entry appears after the epoch bump
    await sh.full.authz.grants.add_grant(None, "role", BASE_ROLE_IDS["user"], GrantSpec("audit.read"))
    await sh.module.epochs.bump("permission")
    assert "authz.audit" in labels(await sh.module.assembler.build(plain))


async def test_disabled_module_hides_entries(sh: ShellHarness) -> None:
    viewer = user(await insert_user(sh.full.database))
    assert "health.services" in labels(await sh.module.assembler.build(viewer))
    await sh.full.administration.toggles.set(SYSTEM_ACTOR, "module", "health", False)
    await sh.module.epochs.bump("module")
    assert "health.services" not in labels(await sh.module.assembler.build(viewer))


async def test_contribution_isolation(sh: ShellHarness) -> None:
    sh.registry.register({"key": "broken.entry", "owner": "module:broken", "kind": "entry", "label_key": "x"})
    sh.registry.register(
        {
            "key": "radio.player",
            "owner": "module:radio",
            "kind": "entry",
            "label_key": "nav.radio",
            "route": "/radio",
            "required_permission": "users.self.manage",
        }
    )
    viewer = user(await insert_user(sh.full.database))
    view = await sh.module.assembler.build(viewer)
    assert "radio.player" in labels(view) and "broken.entry" not in labels(view)
    await sh.module.flush_diagnostics()
    errors = await sh.module.isolator.errors()
    assert [(e["owner"], e["key"], e["reason"]) for e in errors] == [
        ("module:broken", "broken.entry", "schema")
    ]
    async with sh.full.database.session() as session:
        published = await session.scalar(
            text("SELECT count(*) FROM core.event_outbox WHERE type = 'navigation.contribution_rejected'")
        )
    assert published == 1


async def test_authorization_failure_is_fail_closed(sh: ShellHarness) -> None:
    class Broken:
        async def is_allowed(self, principal: Principal, permission: str, resource: object = None) -> bool:
            raise RuntimeError("authz down")

    sh.module.assembler.authorizer = Broken()  # type: ignore[assignment]
    view = await sh.module.assembler.build(user(await insert_user(sh.full.database)))
    assert view["degraded"] is True and view["groups"] == [] and view["commands"] == []
