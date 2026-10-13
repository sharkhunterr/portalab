"""#98 — what waits for someone, as badges on the navigation: every ``shell.attention`` provider is asked,
their counts added up per entry; one that fails counts nothing, and a count of zero is left out."""

from collections.abc import Mapping

from portalab.capabilities.navigation.attention import ATTENTION
from portalab.core.authz_port import Principal
from tests.authz_fixtures import insert_user, user
from tests.integration.shell.conftest import ShellHarness


class _Waiting:
    def __init__(self, counts: Mapping[str, int]) -> None:
        self.values = dict(counts)

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        return self.values


class _Broken:
    async def counts(self, principal: Principal) -> Mapping[str, int]:
        raise RuntimeError("down")


async def test_badges_add_up_and_survive_a_failing_source(sh: ShellHarness) -> None:
    registry = sh.full.identity.capabilities
    registry.provide(
        ATTENTION, _Waiting({"shop.requests": 2, "media.requests": 0}), instance_ref="a", owner="t"
    )
    registry.provide(
        ATTENTION, _Waiting({"shop.requests": 1, "community.moderation": 3}), instance_ref="b", owner="t"
    )
    registry.provide(ATTENTION, _Broken(), instance_ref="c", owner="t")
    member = user(await insert_user(sh.full.database))
    counts = await sh.module.attention(member)
    assert counts.get("shop.requests") == 3 and counts.get("community.moderation") == 3
    assert "media.requests" not in counts
