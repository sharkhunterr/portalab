"""018 T035 (F12) — ``ai.invoke`` for automations (019): read-only tool policy (no write/sensitive tool is
ever offered), capped plain text, runs as the given principal, fails with ``ai.unavailable``."""

from uuid import UUID

import pytest

from portalab.capabilities.ai import INVOKE
from portalab.capabilities.ai.testkit import call
from portalab.core.authz_port import Principal
from portalab.modules.ai.errors import AiUnavailable
from tests.integration.ai.conftest import AiHarness, Recorder, make_tool

pytestmark = pytest.mark.integration


async def test_invoke_is_read_only(ai: AiHarness, people: dict[str, UUID]) -> None:
    writer, purge, reader = Recorder(), Recorder(), Recorder()
    ai.tools.register(make_tool("demo.write", "ai.use", "write", writer))
    ai.tools.register(make_tool("demo.purge", "ai.use", "sensitive", purge))
    ai.tools.register(make_tool("demo.read", "ai.use", "read", reader))
    invoker = ai.full.identity.capabilities.system_providers(INVOKE)[0].provider
    automation = Principal(channel="automation", acting_for=people["ursula"])
    ai.provider.turns = [[call("demo.write", "c1"), call("demo.read", "c2")], ["x" * 10_000]]
    text = await invoker.invoke("Summarize the week", automation, max_tokens=100)
    assert len(text) == 400
    offered = {t.name for t in ai.provider.calls[0][1]}
    assert "demo__read" in offered and not {"demo__write", "demo__purge"} & offered
    assert writer.calls == [] and len(reader.calls) == 1
    assert reader.calls[0][0].acting_for == people["ursula"]
    ai.provider.fail = "unreachable"
    with pytest.raises(AiUnavailable):
        await invoker.invoke("x", automation)
