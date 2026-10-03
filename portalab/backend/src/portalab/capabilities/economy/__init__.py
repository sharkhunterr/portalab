"""Economy & progression contracts (spec 013, contracts/economy-contracts.md).

Exactly **three separate values** — ``xp``, ``contribution`` and ``coins`` — recorded in one append-only
ledger owned by Gamification; Levels are derived from XP and never spendable. Other modules never touch the
ledger: they call these ports.

* ``economy.service`` — ``EconomyService``: spend / refund / reserve / release / consume Coins (Marketplace
  and Community funding, 015/012), balance and history; atomic, never negative, idempotent; an optional
  caller session makes multi-module operations atomic.
* ``economy.rewards`` — ``RewardService``: bounded manual grants (``rewards.grant``), automation grants
  (019, author-bounded) and Contribution grants (016 conversion) — all subject to anti-abuse.
* ``economy.modifiers`` — ``ModifierProvider`` (implemented by Campaigns 014): multiplicative factors valid
  at an event's ``occurred_at``; the combination is capped by ``economy.maxTotalBoost``.
* ``economy.definition_sources`` — ``DefinitionSource``: extra achievement definitions (campaign-scoped).
* ``gamification.progression`` — ``ProgressionReader`` (declared by 017, implemented here).
There is deliberately no conversion between values and no way to create Coins from money.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict

ECONOMY = "economy.service"
REWARDS = "economy.rewards"
MODIFIERS = "economy.modifiers"
DEFINITION_SOURCES = "economy.definition_sources"

Value = Literal["xp", "contribution", "coins"]
VALUES: tuple[Value, ...] = ("xp", "contribution", "coins")
TxKind = Literal[
    "grant",
    "spend",
    "refund",
    "correction",
    "destruction",
    "manual",
    "reserve",
    "reserve_release",
    "reserve_consume",
]
SourceKind = Literal[
    "reward_rule",
    "achievement",
    "quest",
    "daily",
    "challenge",
    "manual",
    "automation",
    "contribution",
    "marketplace",
    "community_funding",
    "system",
]


class InsufficientCoins(Conflict):
    default_code = "economy.insufficient_coins"
    default_title = "Not enough Coins"


@dataclass(frozen=True, slots=True)
class Transaction:
    id: UUID
    seq: int
    user_id: UUID
    value: Value
    delta: int
    kind: str
    source_kind: str
    source_ref: str | None
    occurred_at: datetime
    recorded_at: datetime
    rule_key: str | None = None
    rule_version: int | None = None
    reason: str | None = None
    reverses_transaction_id: UUID | None = None
    duplicate: bool = False  # an idempotent replay returned the existing transaction


@dataclass(frozen=True, slots=True)
class Reservation:
    id: UUID
    user_id: UUID
    amount: int
    source_kind: str
    source_ref: str
    status: Literal["active", "released", "consumed", "destroyed"]


@dataclass(frozen=True, slots=True)
class HistoryPage:
    items: Sequence[Transaction]
    next_cursor: str | None = None


@runtime_checkable
class EconomyService(Protocol):
    async def spend(
        self,
        user: UUID,
        amount: int,
        *,
        reason: str,
        source_kind: str,
        source_ref: str,
        idempotency_key: str,
        session: Any | None = None,
    ) -> Transaction: ...

    async def refund(
        self, transaction_id: UUID, *, reason: str, idempotency_key: str, session: Any | None = None
    ) -> Transaction: ...

    async def balance(self, user: UUID, value: Value) -> int: ...

    async def history(
        self, user: UUID, *, value: Value | None = None, cursor: str | None = None, limit: int = 50
    ) -> HistoryPage: ...

    async def reserve(
        self,
        user: UUID,
        amount: int,
        *,
        source_ref: str,
        idempotency_key: str,
        source_kind: str = "community_funding",
        session: Any | None = None,
    ) -> Reservation: ...

    async def release(
        self, reservation_id: UUID, *, reason: str, session: Any | None = None
    ) -> Reservation: ...

    async def consume(self, reservation_id: UUID, *, session: Any | None = None) -> Reservation: ...


@runtime_checkable
class RewardService(Protocol):
    async def grant_manual(
        self, actor: Principal, user: UUID, value: Value, amount: int, *, reason: str, idempotency_key: str
    ) -> Transaction | None: ...

    async def grant_via_automation(
        self,
        principal: Principal,
        user: UUID,
        value: Value,
        amount: int,
        *,
        automation_ref: str,
        idempotency_key: str,
    ) -> Transaction | None: ...


@dataclass(frozen=True, slots=True)
class Modifier:
    source_ref: str  # ``campaign:<id>``…
    factor: float


@runtime_checkable
class ModifierProvider(Protocol):
    async def modifiers_for(
        self, user: UUID, event_type: str, value: Value, at: datetime
    ) -> Sequence[Modifier]: ...


@dataclass(frozen=True, slots=True)
class ExternalDefinition:
    """An achievement contributed by another module (e.g. a campaign), valid within its window."""

    key: str
    version: int
    definition: Mapping[str, Any]
    effective_from: datetime
    ends_at: datetime | None = None
    source_ref: str = ""


@runtime_checkable
class DefinitionSource(Protocol):
    async def achievements(self, at: datetime) -> Sequence[ExternalDefinition]: ...


@dataclass(frozen=True, slots=True)
class Progress:
    user_id: UUID
    xp: int
    level: int
    level_floor: int
    next_level_at: int | None
    contribution: int
    coins: int
    reserved: int = 0
    achievements: int = 0
    extra: Mapping[str, Any] = field(default_factory=dict)


def _spec(name: str, protocol: type[Any], multi: bool, description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=multi, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(ECONOMY, EconomyService, False, "Coins spending, refunds and reservations (Gamification 013)"),
    _spec(REWARDS, RewardService, False, "Bounded manual and automation grants (Gamification 013)"),
    _spec(MODIFIERS, ModifierProvider, True, "Campaign reward modifiers (Campaigns 014)"),
    _spec(DEFINITION_SOURCES, DefinitionSource, True, "Extra achievement definitions (Campaigns 014)"),
)
