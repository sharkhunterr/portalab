"""003 T012 — AI / automation / plugin principals never exceed the acting user's rights; unknown or
system channels are denied; the AI additionally needs ``ai.use``."""

from uuid import uuid4

import pytest

from portalab.core.authz_port import Principal
from portalab.modules.authz.engine.engine import AuthorizationEngine, PermissionInfo
from portalab.modules.authz.grants.store import EffectiveGrants, GrantRow

pytestmark = pytest.mark.unit

ALICE = uuid4()


def _engine(rows: tuple[GrantRow, ...]) -> AuthorizationEngine:
    engine = AuthorizationEngine.__new__(AuthorizationEngine)

    async def permission(key: str) -> PermissionInfo | None:
        return PermissionInfo(key, True, False, False, False)

    async def effective(subject: object) -> EffectiveGrants:
        assert subject == ALICE
        return EffectiveGrants(ALICE, False, frozenset(), frozenset(), rows)

    engine._permission = permission  # type: ignore[method-assign]
    engine._grants = effective  # type: ignore[method-assign]
    return engine


READ = GrantRow("news.read", "allow", "global", "")
AI_USE = GrantRow("ai.use", "allow", "global", "")


@pytest.mark.parametrize("channel", ["ai", "automation", "plugin"])
async def test_delegated_channels_never_exceed_the_user(channel: str) -> None:
    engine = _engine((READ, AI_USE))
    acting = Principal(channel=channel, acting_for=ALICE)  # type: ignore[arg-type]
    assert (await engine._evaluate(acting, "news.read", None)).allowed
    assert not (await engine._evaluate(acting, "news.publish", None)).allowed
    assert not (await engine._evaluate(Principal(channel=channel), "news.read", None)).allowed  # type: ignore[arg-type]


async def test_ai_needs_ai_use() -> None:
    engine = _engine((READ,))
    decision = await engine._evaluate(Principal(channel="ai", acting_for=ALICE), "news.read", None)
    assert not decision.allowed and decision.reason == "ai_not_permitted"
    assert (
        await engine._evaluate(Principal(channel="automation", acting_for=ALICE), "news.read", None)
    ).allowed


async def test_system_and_unknown_channels_are_denied() -> None:
    engine = _engine((READ,))
    assert not (await engine._evaluate(Principal(channel="system"), "news.read", None)).allowed
    rogue = Principal(user_id=ALICE, channel="root")  # type: ignore[arg-type]
    assert (await engine._evaluate(rogue, "news.read", None)).reason == "channel_not_authorized"
    assert (await engine._evaluate(Principal(), "news.read", None)).reason == "anonymous"
