"""Marketplace event types (T002; via 007, ids and amounts only): ``project.status_changed`` (dedup
``(project, seq)``), ``project.funding_added|funding_released|funding_consumed`` (slice A);
``marketplace.purchase|unlock|refund|grant|revocation|product_published|product_archived`` (slice B);
``marketplace.booster_opened`` (#103)."""

from typing import Literal

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:marketplace"


class StatusChanged(BaseModel):
    project: str
    proposal: str
    from_state: str | None
    to_state: str
    seq: int


class FundingMoved(BaseModel):
    project: str
    funding: str
    amount: int


class ProductChanged(BaseModel):
    product: str
    version: int


class OwnershipChanged(BaseModel):
    product: str
    ownership: str
    price: int = 0


class BoosterOpened(BaseModel):
    """#103: a booster opened — how many cards, how many new, the rarest one."""

    booster: str
    opening: str
    cards: int
    new: int
    best: Literal["common", "rare", "epic", "legendary"]
    price: int = 0


def register_event_types(registry: EventTypeRegistry) -> None:
    if registry.get("marketplace.booster_opened") is None:
        registry.register(
            EventType(
                name="marketplace.booster_opened",
                owner=OWNER,
                schema=BoosterOpened,
                open_payload=False,
                rewardable=frozenset({"cards", "new", "best", "price"}),
                aggregatable=frozenset({"booster", "best"}),
                visibility_class="private",
            )
        )
    for kind, model, scope in (
        ("marketplace.purchase", OwnershipChanged, "private"),
        ("marketplace.unlock", OwnershipChanged, "private"),
        ("marketplace.refund", OwnershipChanged, "private"),
        ("marketplace.grant", OwnershipChanged, "private"),
        ("marketplace.revocation", OwnershipChanged, "private"),
        ("marketplace.product_published", ProductChanged, "community"),
        ("marketplace.product_archived", ProductChanged, "community"),
    ):
        if registry.get(kind) is None:
            registry.register(
                EventType(
                    name=kind,
                    owner=OWNER,
                    schema=model,
                    open_payload=False,
                    automatable=kind in ("marketplace.purchase", "marketplace.product_published"),
                    rewardable=frozenset({"price"}) if model is OwnershipChanged else frozenset(),
                    aggregatable=frozenset(
                        {"product", "price"} if model is OwnershipChanged else {"product"}
                    ),
                    visibility_class=scope,  # type: ignore[arg-type]
                )
            )
    for name, schema, visibility, aggregatable in (
        ("project.status_changed", StatusChanged, "community", frozenset({"to_state"})),
        ("project.funding_added", FundingMoved, "private", frozenset({"amount"})),
        ("project.funding_released", FundingMoved, "private", frozenset({"amount"})),
        ("project.funding_consumed", FundingMoved, "private", frozenset({"amount"})),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    automatable=True,
                    aggregatable=aggregatable,
                    visibility_class=visibility,  # type: ignore[arg-type]
                )
            )
