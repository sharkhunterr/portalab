"""016 T009/T012/T015 — users see incidents but only the affected services they may see; an open incident is
surfaced for its service (006 ``open_for_service`` through the real port, the 006 service-page section);
025 escalation through the port after validation creates exactly one incident and later attaches evidence;
the open-incidents widget and the incidents search provider follow the same rule; notifications go
through the port when present."""

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.notifications import WithPermission
from portalab.capabilities.search import ParsedQuery
from portalab.core.authz_port import Principal
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


async def test_visibility_and_surfacing(
    app: FastAPI, client: httpx.AsyncClient, support: SupportHarness
) -> None:
    notifier = support.outbox  # the harness records ``notifications.send``
    boss = await create_user(module_of(app), "boss")
    await make_admin(support.full, boss)
    await login(client, "boss")
    created = (
        await client.post(
            "/api/v1/admin/incidents",
            json={"title": "Books offline", "severity": "critical", "service_ids": ["s2", "s9"]},
        )
    ).json()
    await support.module.notifier.drain()
    [request] = notifier.sent
    assert (
        request.kind == "alert"
        and request.priority == "critical"
        and request.dedup_key.endswith(":created:1")  # issue 398: per version, every update is told
        and request.params["severity"] == "critical"
    )
    assert isinstance(request.audience, WithPermission) and request.audience.service_ids == ("s2", "s9")
    assert created["evidence"] == [] and {s["id"] for s in created["services"]} == {"s2", "s9"}

    alex = await create_user(module_of(app), "alex")
    await login(client, "alex")
    seen = (await client.get(f"/api/v1/incidents/{created['id']}")).json()
    assert seen["services"] == [{"id": "s2", "name": "Books"}]  # s9 is unknown to the viewer: not revealed
    assert all(u["author_user_id"] is None for u in seen["updates"]) and seen["source"] == "manual"
    open_ = (await client.get("/api/v1/incidents", params={"state": "open", "service": "s2"})).json()
    assert [i["id"] for i in open_] == [created["id"]]

    refs = await support.module.port.open_for_service("s2")
    assert [r.id for r in refs] == [created["id"]] and refs[0].extra["number"] == "INC-0001"
    widget = await support.widgets.get("support.open_incidents").provider.load(
        Principal(user_id=alex), {}, LocaleContext()
    )  # type: ignore[union-attr]
    assert widget.data["items"][0]["route"] == f"/incidents/{created['id']}"  # type: ignore[index]
    first = widget.data["items"][0]  # type: ignore[index]
    assert (first["severity"], first["state"], first["services"], widget.data["open"]) == (  # type: ignore[index]
        "critical",
        "investigating",
        2,
        1,
    )
    # 027: an incident in the calendar lasts from its start until now while it runs
    from datetime import timedelta

    from portalab.capabilities.content import default_calendar_sources
    from portalab.core.time import utc_now
    from portalab.modules.support.incidents.integrations import IncidentCalendarSource

    assert default_calendar_sources.get("incident") is not None  # registered by the module
    source = IncidentCalendarSource(support.module.incidents, support.module.clock)
    now = utc_now(support.module.clock)
    found = await source.items(
        now - timedelta(days=1), now + timedelta(days=1), Principal(user_id=alex), LocaleContext()
    )
    [item] = [i for i in found.items if i.source_id == created["id"]]
    assert item.type == "incident" and item.category == "critical" and item.ends_at is not None
    assert item.title == "INC-0001 · Books offline" and item.url_ref == f"/incidents/{created['id']}"
    provider = support.search.provider("incidents")
    query = ParsedQuery(text="books", normalized="books", terms=("books",))
    found = await provider.search(query, Principal(user_id=alex), LocaleContext(), limit=5, cursor=None)  # type: ignore[union-attr]
    assert [i.title for i in found.items] == ["INC-0001 · Books offline"]


async def test_observability_escalation_creates_one_incident(support: SupportHarness) -> None:
    port = support.module.port
    evidence = {"anomaly_id": "an-1", "detector": "error_rate", "component": "media", "summary": "5xx burst"}
    first = await port.create(
        title="error rate on media", source="observability", severity="critical", evidence=evidence
    )
    again = await port.create(
        title="error rate on media", source="observability", severity="critical", evidence=evidence
    )
    assert first.id == again.id
    attached = await port.attach(first.id, {"anomaly_id": "an-1", "occurrences": 3})
    assert attached is not None
    view = await support.module.incidents.get(__import__("uuid").UUID(first.id))
    assert view.evidence == ["observability:anomaly:an-1"]  # pointer only, no payload


async def test_service_back_closes_only_the_portals_incidents(support: SupportHarness) -> None:
    """027: when a service is back, Health closes the incidents it declared for it — never one a person
    opened; declaring twice for the same outage gives one incident."""
    port = support.module.port
    one = await port.create(
        title="Plex is not responding",
        source="health",
        severity="major",
        evidence={"service_id": "s9"},
        service_ids=["s9"],
        dedup_key="outage:s9:3",
    )
    again = await port.create(
        title="Plex is not responding",
        source="health",
        severity="major",
        evidence={"service_id": "s9"},
        service_ids=["s9"],
        dedup_key="outage:s9:3",
    )
    assert again.id == one.id
    manual, _ = await support.module.incidents.create(
        None, title="Plex is slow", severity="minor", source="manual", service_ids=["s9"]
    )
    assert await port.resolve_for_service("s9", source="health", message="Plex answers again.") == 1
    still = {ref.id for ref in await port.open_for_service("s9")}
    assert still == {str(manual.id)}
