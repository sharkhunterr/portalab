"""#298 — a statistic's « source » dimension: the event's own source (where a reward comes from) before the
system that sent it."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from portalab.capabilities.events import Envelope
from portalab.modules.statistics.projection.consumers import field_value


def envelope(payload: dict[str, Any]) -> Envelope:
    now = datetime(2026, 10, 31, tzinfo=UTC)
    return Envelope(
        event_id=uuid4(),
        seq=1,
        type="reward.granted",
        type_version=1,
        occurred_at=now,
        received_at=now,
        source_system="portalab",
        source_event_id=None,
        actor_user_id=None,
        actor_kind="system",
        subject_type=None,
        subject_id=None,
        payload=payload,
        provenance={},
        correlation_id=None,
    )


def test_a_reward_counts_under_where_it_comes_from() -> None:
    assert field_value(envelope({"value": "xp", "amount": 5, "source": "daily"}), "source") == "daily"


def test_an_event_without_a_source_of_its_own_counts_under_its_sender() -> None:
    assert field_value(envelope({"value": "xp"}), "source") == "portalab"
