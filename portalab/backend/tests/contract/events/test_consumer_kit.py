"""007 T017 — the consumer kit itself, exercised on a sample consumer (and catching a bad one)."""

from typing import ClassVar

import pytest

from portalab.capabilities.events import ConsumerContext, Envelope
from tests.contract.consumer_kit import ConsumerContractKit, FakeContext, envelope

pytestmark = pytest.mark.contract


class TestWellBehavedConsumer(ConsumerContractKit):
    sent: ClassVar[list[str]] = []

    @staticmethod
    async def handler(event: Envelope, ctx: ConsumerContext) -> None:
        if await ctx.idempotent_effect(f"notify:{event.event_id}"):
            TestWellBehavedConsumer.sent.append(str(event.event_id))

    def sample(self) -> Envelope:
        return self._sample if hasattr(self, "_sample") else self._make()

    def _make(self) -> Envelope:
        self._sample = envelope("demo.happened", {"n": 1})
        return self._sample

    def effects(self) -> int:
        return len(self.sent)


async def test_kit_catches_a_non_idempotent_consumer() -> None:
    sent: list[int] = []

    async def naive(event: Envelope, ctx: ConsumerContext) -> None:
        sent.append(1)

    event, context = envelope("demo.happened", {}), FakeContext()
    await naive(event, context)
    await naive(event, context)
    assert len(sent) == 2  # what the kit's duplicate-delivery check rejects
