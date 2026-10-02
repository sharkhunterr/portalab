"""008 T027 — ``/palette/resolve`` returns only permitted destinations/actions; context actions depend on
the route; object references open directly when permitted; sensitive actions carry
``confirmation_required``; unknown or forbidden references reveal nothing."""

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.search import ActionDef
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.search.conftest import SearchHarness
from tests.unit.search.fakes import FakeProvider, FakeResolver

pytestmark = pytest.mark.integration


async def test_palette(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    assert (await client.get("/api/v1/palette/resolve")).status_code == 401
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    search.registry.register_action(
        ActionDef(
            "services.restart",
            "action.restart",
            "services.read",
            "destructive",
            action_id="services.restart",
            context_route="/services/",
        ),
        owner="module:health",
    )
    search.registry.register_action(
        ActionDef("audit.export", "action.export", "audit.read", context_route="/admin/audit"),
        owner="module:audit",
    )
    search.registry.register(FakeProvider("tickets", permission="audit.read"), owner="module:support")
    search.registry.register_resolver(FakeResolver("tickets", {"123": "Printer"}), owner="module:support")

    home = (await client.get("/api/v1/palette/resolve", params={"route": "/"})).json()
    assert [d["route"] for d in home["destinations"]] == ["/services"]  # not /admin/audit
    assert home["actions"] == []
    page = (await client.get("/api/v1/palette/resolve", params={"route": "/services/s1"})).json()
    [restart] = page["actions"]
    assert restart["id"] == "services.restart" and restart["confirmation_required"] is True
    audit_page = (await client.get("/api/v1/palette/resolve", params={"route": "/admin/audit"})).json()
    assert audit_page["actions"] == []  # forbidden context action stays hidden

    go = (await client.get("/api/v1/palette/resolve", params={"q": "open services"})).json()
    assert go["intent"] == {
        "type": "navigate",
        "target": "health.services",
        "query": None,
        "route": "/services",
    }
    svc = (await client.get("/api/v1/palette/resolve", params={"q": "portalab://services/s2"})).json()
    assert svc["object"] == {"kind": "services", "id": "s2", "title": "Café Books", "route": "/services/s2"}
    for ref in ("#123", "portalab://tickets/123", "portalab://services/nope", "portalab://nothing/1"):
        hidden = (await client.get("/api/v1/palette/resolve", params={"q": ref})).json()
        assert hidden["object"] is None, ref
    bad = await client.get("/api/v1/palette/resolve", params={"route": "javascript:alert(1)"})
    assert bad.status_code == 422
