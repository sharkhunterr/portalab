"""018 T024/T025 — ``navigate.suggest`` proposes only routes present in the user's own navigation view;
unpermitted destinations are omitted without a trace; explain-this-page uses the conversation's page
context and 011 help pages; auto-navigation stays off unless the Admin enables it."""

from collections.abc import Sequence
from uuid import UUID

import httpx
import pytest

from portalab.capabilities.ai.testkit import call
from portalab.capabilities.content import HELP, KnowledgeHit
from portalab.capabilities.navigation import NavigationContribution
from portalab.core.authz_port import Principal
from tests.integration.ai.conftest import AiHarness, done, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


class FakeHelp:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def for_context(self, key: str, principal: Principal) -> Sequence[KnowledgeHit]:
        self.keys.append(key)
        return [
            KnowledgeHit(
                "portalab://wiki/7", "Using the services page", "How to read states.", "/wiki/services"
            )
        ]


def contributions(ai: AiHarness) -> None:
    for key, route, permission, keywords in (
        ("shell.services", "/services", "services.read", ("status", "services")),
        ("shell.users", "/admin/users", "users.manage", ("users", "accounts", "services")),
        ("shell.wiki", "/wiki", "wiki.read", ("docs",)),
    ):
        ai.navigation.register(
            NavigationContribution(
                key=key,
                owner="module:shell",
                kind="entry",
                label_key=f"nav.{key}",
                route=route,
                required_permission=permission,
                keywords=keywords,
            )
        )


async def test_suggestions_are_bounded_by_the_users_navigation(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    contributions(ai)
    tool = ai.module.baseline
    user = await tool.navigate(
        Principal(channel="ai", acting_for=people["ursula"]), {"query": "services users"}
    )
    admin = await tool.navigate(
        Principal(channel="ai", acting_for=people["boss"]), {"query": "services users"}
    )
    assert [s["route"] for s in user.data["suggestions"]] == ["/services"]
    assert {s["route"] for s in admin.data["suggestions"]} == {"/services", "/admin/users"}
    ai.provider.turns = [[call("navigate.suggest", "c1", query="accounts")], ["Nothing for you there."]]
    await login(client, "ursula")
    events = await say(client, await start(client), "where do I manage accounts?")
    assert not [d for n, d in events if n == "source"]  # /admin/users never mentioned
    assert (await client.get("/api/v1/ai/status")).json()["auto_navigate"] is False


async def test_explain_this_page(ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]) -> None:
    help_port = FakeHelp()
    ai.full.identity.capabilities.provide(HELP, help_port, instance_ref="t", owner="module:wiki")
    ai.provider.turns = [[call("help.page", "c1", page="/services")], ["This page lists services [1]."]]
    await login(client, "ursula")
    events = await say(
        client, await start(client, {"route": "/services", "title": "Services"}), "explain this page"
    )
    system = ai.provider.calls[0][0][0].content
    assert '"/services"' in system and '"Services"' in system
    assert help_port.keys == ["/services"]
    answer = done(events)
    assert answer["sources"][0]["class"] == "knowledge" and answer["interpretation"] is False
