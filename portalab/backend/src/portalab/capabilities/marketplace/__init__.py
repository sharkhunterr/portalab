"""Marketplace contracts (spec 015, contracts/marketplace-contracts.md).

Slice A — the **community funding lifecycle** (CD-008): Community (012) registers each project proposal
and reads its state through ``ProjectLifecycle``; Marketplace owns the state machine, the per-project
funding rules and the Coins *reserved* by funders (held by the 013 ledger, never by Marketplace).

Slice B adds the catalog (``marketplace.entitlements``, already declared for 009 widget products).
"""

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

LIFECYCLE = "marketplace.project_lifecycle"

ProjectState = Literal[
    "idea", "proposal", "open", "validation", "development", "beta", "released", "rejected", "abandoned"
]
PROJECT_STATES: tuple[ProjectState, ...] = (
    "idea",
    "proposal",
    "open",
    "validation",
    "development",
    "beta",
    "released",
    "rejected",
    "abandoned",
)
VOTING_STATES: frozenset[str] = frozenset({"idea", "proposal", "open"})
TERMINAL_STATES: frozenset[str] = frozenset({"released", "rejected", "abandoned"})


@dataclass(frozen=True, slots=True)
class ProjectRef:
    id: UUID
    state: ProjectState


@dataclass(frozen=True, slots=True)
class FundingSummary:
    """Public aggregates only — never who funded."""

    state: ProjectState
    accepts_funding: bool
    reserved: int
    consumed: int
    funders: int
    goal_amount: int | None = None


@runtime_checkable
class ProjectLifecycle(Protocol):
    """Provided by Marketplace to Community: one lifecycle record per proposal (idempotent ``register``);
    the state is read from here, never stored by Community."""

    async def register(self, proposal_ref: str, proposer: UUID | None, title: str) -> ProjectRef: ...

    async def state(self, project_ref: str) -> ProjectState | None: ...

    async def accepts_votes(self, project_ref: str) -> bool: ...

    async def funding_summary(self, project_ref: str) -> FundingSummary | None: ...


LIFECYCLE_SPEC = CapabilitySpec(
    name=LIFECYCLE,
    version="1.0",
    protocol=ProjectLifecycle,
    multi_provider=False,
    description="Community project lifecycle and funding summary (Marketplace 015)",
)
SPECS: tuple[CapabilitySpec, ...] = (LIFECYCLE_SPEC,)
