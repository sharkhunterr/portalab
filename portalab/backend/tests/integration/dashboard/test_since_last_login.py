"""009 T027/T029 — "Since Last Login": aggregates provider items after the boundary, permission-scoped per
principal (a user without ``services.read`` sees no service change); a failing provider is reported, not
fatal; the boundary only advances on ``seen`` (never backwards), so two sessions do not lose items;
lookback cap and item cap."""

from dataclasses import replace
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.dashboard import ChangeItem
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from tests.integration.dashboard.conftest import DashboardHarness
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.privacy.conftest import NOW

pytestmark = pytest.mark.integration


class News:
    kind = "news"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def changes_since(
        self, principal: Principal, since: datetime, limit: int, ctx: LocaleContext
    ) -> list[ChangeItem]:
        if self.fail:
            raise RuntimeError("news down")
        items = [
            ChangeItem("news", NOW - timedelta(days=days), f"/news/{days}", title=f"News {days}")
            for days in (40, 10, 2)
        ]
        return [i for i in items if i.occurred_at > since][:limit]


async def test_summary(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    dash.registry.register_summary(News(), owner="module:news")
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    summary = (await client.get("/api/v1/dashboard/since-last-login")).json()
    titles = [i["title"] or i["title_args"].get("name") for i in summary["items"]]
    # service changes first (priority, the outage highest); the 40-day-old item is outside the lookback
    assert titles == ["Books", "Media", "News 2", "News 10"]
    assert summary["items"][0]["title_key"] == "dashboard:summary.serviceState"
    seen = (
        await client.post(
            "/api/v1/dashboard/since-last-login/seen", json={"until": (NOW - timedelta(days=5)).isoformat()}
        )
    ).json()
    assert seen["since"].startswith((NOW - timedelta(days=5)).date().isoformat())
    older = await client.post(
        "/api/v1/dashboard/since-last-login/seen", json={"until": (NOW - timedelta(days=20)).isoformat()}
    )
    assert older.json()["since"] == seen["since"]  # never backwards (another session acknowledged later)
    after = (await client.get("/api/v1/dashboard/since-last-login")).json()
    assert [i["ref"] for i in after["items"]] == ["/services/s2", "/services/s1", "/news/2"]
    dash.module.config = replace(dash.module.config, max_items=1)
    assert len((await client.get("/api/v1/dashboard/since-last-login")).json()["items"]) == 1


async def test_summary_is_scoped_and_resilient(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    dash.registry.register_summary(News(fail=True), owner="module:news")
    user = await create_user(module_of(app), "alex")
    summary = await dash.module.summary.summary(Principal(channel="ai", acting_for=user), LocaleContext())
    assert summary.unavailable == ["news"]
    from tests.unit.dashboard.fakes import Authorizer

    services = next(p for p in dash.registry.summaries() if p.kind == "services")
    services.provider.authorizer = Authorizer(set())  # type: ignore[attr-defined]
    await login(client, "alex")
    body = (await client.get("/api/v1/dashboard/since-last-login")).json()
    assert body["items"] == [] and body["unavailable"] == ["news"]
