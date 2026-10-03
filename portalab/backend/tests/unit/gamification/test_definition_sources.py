"""013 T034 (F5) — achievement evaluation also reads campaign-scoped definitions from ``DefinitionSource``
providers while their window is open; own definitions win on a key clash; a failing source is ignored."""

from collections.abc import Sequence
from datetime import datetime, timedelta

import pytest

from portalab.capabilities.economy import DEFINITION_SOURCES, ExternalDefinition


class Campaign:
    def __init__(self, start: datetime, end: datetime) -> None:
        self.start, self.end = start, end

    async def achievements(self, at: datetime) -> Sequence[ExternalDefinition]:
        return [
            ExternalDefinition(
                "halloween_watcher",
                1,
                {
                    "label": "Halloween watcher",
                    "criteria": [{"kind": "event_count", "event_type": "media.played", "count": 2}],
                },
                self.start,
                self.end,
                "campaign:halloween",
            ),
            ExternalDefinition(
                "bad", 1, {"label": "x", "criteria": []}, self.start, self.end, "campaign:halloween"
            ),
        ]


class Broken:
    async def achievements(self, at: datetime) -> Sequence[ExternalDefinition]:
        raise RuntimeError("campaigns down")


@pytest.mark.integration
async def test_campaign_definitions(gm) -> None:  # type: ignore[no-untyped-def]
    now = gm.clock.now()
    capabilities = gm.ev.full.identity.capabilities
    capabilities.provide(
        DEFINITION_SOURCES, Campaign(now, now + timedelta(days=1)), instance_ref="c", owner="module:campaigns"
    )
    capabilities.provide(DEFINITION_SOURCES, Broken(), instance_ref="b", owner="module:campaigns")
    keys = [d.key for d in await gm.module.achievements.definitions(now + timedelta(hours=1))]
    assert keys == ["halloween_watcher"]  # the invalid one is ignored, the broken source too
    assert await gm.module.achievements.definitions(now + timedelta(days=2)) == []
    user = gm.people["ursula"]
    for i in range(2):
        await gm.module.pipeline.process(gm.envelope(user, at=now + timedelta(minutes=i + 1)))
    unlocked = await gm.module.achievements.progress(user)
    assert unlocked[0]["key"] == "halloween_watcher" and unlocked[0]["state"] == "unlocked"
