"""Marketplace contracts (spec 015, contracts/marketplace-contracts.md).

Slice A — the **community funding lifecycle** (CD-008): Community (012) registers each project proposal
and reads its state through ``ProjectLifecycle``; Marketplace owns the state machine, the per-project
funding rules and the Coins *reserved* by funders (held by the 013 ledger, never by Marketplace).

Slice B — the catalog: an owner-tagged **product type registry** (``register_product_type``) where each
type brings an ``ActivationHandler`` run after acquisition; ownership is read by other modules through
``marketplace.entitlements`` (declared with 009 widget products).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable
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
    title: str | None = None  # #314: what the journals name a funding by


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
GIFTS = "marketplace.gifts"


@runtime_checkable
class Gifts(Protocol):
    """027: offer a product to a member on the portal's behalf (a level reward…) — ``False`` when the
    product is unknown or already owned; never charged."""

    async def gift(self, user: UUID, product_key: str, reason: str) -> bool: ...


GIFTS_SPEC = CapabilitySpec(
    name=GIFTS,
    version="1.0",
    protocol=Gifts,
    multi_provider=False,
    description="Offer a shop product to a member (level rewards, 027)",
)

SPECS: tuple[CapabilitySpec, ...] = (LIFECYCLE_SPEC, GIFTS_SPEC)


# --- slice B: product types and activation ------------------------------------------------------------
ActivationState = Literal["active", "needs_configuration", "failed", "incompatible"]


@dataclass(frozen=True, slots=True)
class OwnershipView:
    """What an activation handler sees of one ownership."""

    id: UUID
    user_id: UUID
    product_key: str
    product_type: str
    payload: Mapping[str, Any] = field(default_factory=dict)  # the product version's type-specific data
    configuration: Mapping[str, Any] = field(default_factory=dict)  # set by the owner when required


@dataclass(frozen=True, slots=True)
class ActivationResult:
    state: ActivationState
    detail: str = ""


@runtime_checkable
class ActivationHandler(Protocol):
    async def activate(self, ownership: OwnershipView) -> ActivationResult: ...

    async def deactivate(self, ownership: OwnershipView) -> None: ...


@dataclass(frozen=True, slots=True)
class ProductType:
    key: str
    owner: str
    handler: ActivationHandler = field(compare=False)
    refundable_by_default: bool = True
    payload_fields: tuple[str, ...] = ()  # allowed keys of a version's ``payload`` (closed set)
    label_key: str = ""


class ProductTypeRegistry:
    def __init__(self) -> None:
        self._types: dict[str, ProductType] = {}

    def register(self, product_type: ProductType) -> ProductType:
        existing = self._types.get(product_type.key)
        if existing is not None and existing.owner != product_type.owner:
            raise ValueError(f"product type {product_type.key!r} is already registered by {existing.owner}")
        if product_type.owner.startswith("plugin:") and not product_type.key.startswith(
            f"plugin:{product_type.owner.removeprefix('plugin:')}"
        ):
            raise ValueError("plugin product types are namespaced 'plugin:<key>.<type>'")
        self._types[product_type.key] = product_type
        return product_type

    def get(self, key: str) -> ProductType | None:
        return self._types.get(key)

    def all(self) -> list[ProductType]:
        return [self._types[k] for k in sorted(self._types)]

    def unregister(self, owner: str) -> int:
        doomed = [k for k, t in self._types.items() if t.owner == owner]
        for key in doomed:
            del self._types[key]
        return len(doomed)


default_product_types = ProductTypeRegistry()


def register_product_type(
    product_type: ProductType, registry: ProductTypeRegistry = default_product_types
) -> ProductType:
    return registry.register(product_type)
