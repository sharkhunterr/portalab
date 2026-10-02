"""025 T029/T032/T034 — standard users denied; Support gets redacted context, the Admin the full context;
no secrets in stored errors; user references are ids, cleared on erasure; ``/metrics`` off by default,
then token- or permission-protected."""

from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY
from portalab.modules.observability.models import ErrorRecord
from tests.authz_fixtures import insert_user
from tests.connectors_fixtures import admin_client
from tests.integration.identity.helpers import create_user, login, module_of
from tests.observability_fixtures import ObsHarness

pytestmark = pytest.mark.integration
EID = "00000000-0000-7000-8000-000000000000"
READ = ["/overview", "/components/events", "/errors", "/anomalies", "/performance", "/trends"]
MANAGE = [
    f"/errors/{EID}/ack",
    f"/errors/{EID}/resolve",
    f"/anomalies/{EID}/validate",
    f"/anomalies/{EID}/dismiss",
]
BASE = "/api/v1/admin/observability"


async def test_matrix_and_tiers(app: FastAPI, client: httpx.AsyncClient, ob: ObsHarness) -> None:
    user_id = await insert_user(ob.database)
    ob.hooks.error(
        "sync",
        "auth",
        RuntimeError("password=hunter2 rejected"),
        context={"service": "s1"},
        user_ref=str(user_id),
    )
    await ob.module.cycle()
    for path in READ:
        assert (await client.get(BASE + path)).status_code == 401, path
    for path in MANAGE:
        assert (await client.post(BASE + path, json={})).status_code == 401, path

    identity = module_of(app)
    await create_user(identity, "plain")
    helper_id = await create_user(identity, "helper")
    await ob.hl.cn.full.authz.grants.assign_role(ob.hl.cn.admin, helper_id, "support")
    await login(client, "plain")
    for path in READ:
        assert (await client.get(BASE + path)).status_code == 403, path

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as support:
        await login(support, "helper")
        [error] = (await support.get(BASE + "/errors")).json()["items"]
        assert "context" not in error and "user_ref" not in error and error["context_keys"] == ["service"]
        assert "hunter2" not in error["message"]
        assert (await support.post(BASE + f"/errors/{error['id']}/ack")).status_code == 403

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as admin:
        await admin_client(app, admin, ob.hl.cn)
        [error] = (await admin.get(BASE + "/errors")).json()["items"]
        assert error["context"] == {"service": "s1"} and error["user_ref"] == str(user_id)
        assert (
            await admin.post(BASE + f"/errors/{error['id']}/resolve", json={"resolution": "rotated the key"})
        ).json()["state"] == "resolved"
        overview = (await admin.get(BASE + "/overview")).json()
        assert {"portal", "problems", "components"} <= set(overview)

    [participant] = [
        r
        for r in ob.hl.cn.full.identity.capabilities.system_providers(ERASURE_CAPABILITY)
        if r.instance_ref == "observability"
    ]
    await participant.provider.erase(user_id, "final")
    async with ob.database.session() as session:
        assert (await session.execute(select(ErrorRecord.user_ref))).scalar_one() is None


async def test_metrics_endpoint(app: FastAPI, client: httpx.AsyncClient, ob: ObsHarness) -> None:
    assert (await client.get("/metrics")).status_code == 404  # disabled by default
    ob.module.config = replace(ob.module.config, metrics_endpoint_enabled=True)
    assert (await client.get("/metrics")).status_code == 401
    assert (await client.get("/metrics", headers={"Authorization": f"Bearer {uuid4()}"})).status_code == 401
    ob.hooks.counter("jobs", "job.succeeded", labels={"kind": "demo"})
    await ob.module.cycle()
    await admin_client(app, client, ob.hl.cn)
    body = (await client.get("/metrics")).text
    assert 'portalab_jobs_job_succeeded_count{kind="demo"} 1' in body
    assert 'portalab_component_health{axis="technical",component="db"} 0' in body
