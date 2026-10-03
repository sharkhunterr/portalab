"""016 T014 — only ``incidents.manage`` mutates; anonymous callers get 401; the public view never exposes
evidence pointers, authors, the detailed source or service names the viewer cannot see; titles and
summaries are returned as plain text (rendered as text by the SPA)."""

import httpx
import pytest
from fastapi import FastAPI

from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


async def test_matrix_and_redaction(app: FastAPI, client: httpx.AsyncClient, support: SupportHarness) -> None:
    view, _ = await support.module.incidents.create(
        None,
        title="<script>alert(1)</script> outage",
        severity="major",
        source="observability",
        service_ids=["s1"],
        evidence=["observability:anomaly:x"],
    )
    routes = [
        ("GET", "/api/v1/incidents"),
        ("GET", f"/api/v1/incidents/{view.id}"),
        ("POST", "/api/v1/admin/incidents"),
        ("POST", f"/api/v1/admin/incidents/{view.id}/updates"),
        ("PATCH", f"/api/v1/admin/incidents/{view.id}"),
        ("POST", f"/api/v1/admin/incidents/{view.id}/resolve"),
    ]
    for method, path in routes:
        assert (await client.request(method, path, json={})).status_code == 401, path
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    for method, path in routes[2:]:
        assert (await client.request(method, path, json={"message": "x"})).status_code == 403, path
    public = (await client.get(f"/api/v1/incidents/{view.id}")).json()
    assert public["evidence"] == [] and public["source"] == "automatic"
    assert public["title"] == "<script>alert(1)</script> outage"  # data, never interpreted server side
