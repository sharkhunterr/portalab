"""014 T021/T028 — readers: ``CampaignReader`` (``is_active``, ``active_for_user``), the 009 widget condition
``campaign_active``, the 011 calendar source and the ``campaigns.active`` widget; Campaigns never computes
final amounts (only factors with references)."""

import pytest

from portalab.capabilities.campaigns import READER, CampaignReader
from portalab.capabilities.economy import MODIFIERS
from portalab.capabilities.i18n import DEFAULT_CONTEXT
from portalab.core.authz_port import Principal
from tests.integration.campaigns.conftest import CampHarness, later, paris

pytestmark = pytest.mark.integration


async def test_readers_and_sources(cm: CampHarness) -> None:
    await cm.create()
    capabilities = cm.ev.full.identity.capabilities
    reader = capabilities.system_providers(READER)[0].provider
    assert isinstance(reader, CampaignReader)
    assert not await reader.is_active("halloween")
    await cm.at(later(paris(10, 20, 0), minutes=1))
    assert await reader.is_active("halloween") and not await reader.is_active("christmas")
    assert [c.key for c in await reader.active_for_user(cm.people["ursula"])] == ["halloween"]
    from portalab.capabilities.dashboard import Condition
    from portalab.modules.dashboard.conditions.evaluator import ConditionEvaluator

    evaluator = ConditionEvaluator(cm.ev.full.authz.engine, capabilities)
    result = await evaluator.evaluate_all([Condition("campaign_active", "halloween")], cm.p("ursula"))
    assert result.passed, result.diagnostics
    source = cm.calendar.get("campaign")
    assert source is not None
    items = (await source.items(paris(10, 1), paris(12, 31), cm.p("ursula"), DEFAULT_CONTEXT)).items
    assert [(i.type, i.title, i.url_ref) for i in items] == [
        ("campaign", "Halloween", "/campaigns/halloween")
    ]
    widget = cm.widgets.get("campaigns.active")
    assert widget is not None
    payload = await widget.provider.load(cm.p("ursula"), {}, DEFAULT_CONTEXT)
    assert payload.state == "available" and payload.data["items"][0]["route"] == "/campaigns/halloween"  # type: ignore[index]
    provider = next(
        p.provider for p in capabilities.system_providers(MODIFIERS) if p.instance_ref == "campaigns"
    )
    assert not any(hasattr(provider, name) for name in ("grant", "record", "spend", "writer"))
    assert await reader.is_active("halloween", paris(10, 1)) is False
    assert Principal is not None
