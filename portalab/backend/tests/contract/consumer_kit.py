"""007 T017 — reusable consumer contract kit: every module's consumer must tolerate duplicate delivery,
crash/redelivery and replay (no side effect when ``ctx.replay``). Subclass and implement the hooks."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from portalab.capabilities.events import Envelope, Handler


class FakeContext:
    def __init__(self, *, replay: bool = False) -> None:
        self.replay = replay
        self.as_of = datetime(2026, 10, 1, tzinfo=UTC)
        self.keys: set[str] = set()

    async def idempotent_effect(self, key: str) -> bool:
        if self.replay or key in self.keys:
            return False
        self.keys.add(key)
        return True


def envelope(event_type: str, payload: dict[str, Any], **extra: Any) -> Envelope:
    values: dict[str, Any] = {
        "event_id": uuid4(),
        "seq": 1,
        "type": event_type,
        "type_version": 1,
        "occurred_at": datetime(2026, 10, 1, tzinfo=UTC),
        "received_at": datetime(2026, 10, 1, tzinfo=UTC),
        "source_system": "test",
        "source_event_id": None,
        "actor_user_id": None,
        "actor_kind": "system",
        "subject_type": None,
        "subject_id": None,
        "payload": payload,
        "provenance": {},
        "correlation_id": None,
    }
    values.update(extra)
    return Envelope(**values)


class ConsumerContractKit:
    """Hooks: ``handler`` (the consumer), ``sample()`` (an envelope it handles), ``effects()`` (count of
    externally visible side effects produced so far)."""

    handler: Handler

    def sample(self) -> Envelope:
        raise NotImplementedError

    def effects(self) -> int:
        raise NotImplementedError

    async def test_duplicate_delivery_has_one_effect(self) -> None:
        context, event = FakeContext(), self.sample()
        await self.handler(event, context)
        await self.handler(event, context)
        assert self.effects() <= 1

    async def test_replay_has_no_effect(self) -> None:
        before = self.effects()
        await self.handler(self.sample(), FakeContext(replay=True))
        assert self.effects() == before
