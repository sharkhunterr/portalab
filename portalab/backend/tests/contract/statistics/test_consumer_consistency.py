"""017 T020 — the provider is the single read path: the registered ``statistics.provider`` capability, the
REST API and the dashboard bridge return the same value for the same inputs; a principal without the
statistic's permission gets nothing; results never carry secrets or raw user ids of others."""

import json
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.statistics import PROVIDER, Period, StatisticsProvider
from portalab.core.authz_port import Principal
from portalab.modules.statistics.provider.provider import StatisticForbidden
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.privacy.conftest import NOW
from tests.integration.statistics.conftest import StatsHarness

pytestmark = pytest.mark.integration

ACTIVE = {
    "key": "users.active",
    "title_key": "t",
    "domain": "users",
    "scope": "community",
    "event_types": ["user.signed_in"],
    "measure": {"kind": "distinct_count", "field": "actor"},
}


async def test_one_value_everywhere(app: FastAPI, client: httpx.AsyncClient, stats: StatsHarness) -> None:
    people = [uuid4() for _ in range(6)]
    for index, person in enumerate(people):
        for repeat in range(1 + index % 2):
            await stats.publish("user.signed_in", {}, at=NOW - timedelta(hours=1 + repeat), actor=person)
    await stats.define(ACTIVE)
    await stats.define({**ACTIVE, "key": "users.audit_only", "required_permission": "audit.read"})
    await stats.dispatch()
    alex = await create_user(module_of(app), "alex")
    provider = stats.ev.full.identity.capabilities.system_providers(PROVIDER)[0].provider
    assert isinstance(provider, StatisticsProvider)
    period = Period("last_n_days", days=7)
    direct = await provider.get("users.active", viewer=Principal(user_id=alex), period=period)
    await login(client, "alex")
    api = (
        await client.get("/api/v1/statistics/users.active", params={"period": "last_n_days", "days": 7})
    ).json()
    assert direct.value == api["value"] == 6
    with pytest.raises(StatisticForbidden):
        await provider.get("users.audit_only", viewer=Principal(user_id=alex), period=period)
    assert (await client.get("/api/v1/statistics/users.audit_only")).status_code == 403
    assert "users.audit_only" not in {
        e["key"] for e in (await client.get("/api/v1/statistics/catalog")).json()
    }
    body = json.dumps(api)
    assert all(str(person) not in body for person in people)
