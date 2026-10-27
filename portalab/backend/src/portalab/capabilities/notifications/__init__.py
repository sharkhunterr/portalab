"""Notifications contracts (spec 010 T006; contracts/notifications-contracts.md).

* ``send(CommunicationRequest, caller=…)`` — the **only** way to produce a communication (modules, admin
  broadcasts, system sources, later the 019 ``communication.produce`` action). No rule engine here.
* four distinct concepts: a *notification* (``kind="notification"``) and an *alert* (``kind="alert"``,
  priority ≥ high) land in the notification center; *e-mail* is only a channel; *news* stays in its module.
* audiences (``Users``, ``WithPermission``, ``Role``, ``AllAuthenticated``) are resolved **under the
  caller's authority** and every recipient is re-authorized at delivery;
* categories are declared by their owners (owner-tagged; plugin categories are ``plugin:<key>.*`` and
  never mandatory).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

NOTIFY = "notifications.send"

Kind = Literal["notification", "alert"]
Priority = Literal["low", "normal", "high", "critical"]
ChannelName = Literal["portal", "email", "sound", "push"]
Source = Literal["system", "admin_rule", "event", "automation", "module"]
PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "critical")
CHANNELS: tuple[str, ...] = ("portal", "email")


@dataclass(frozen=True, slots=True)
class Users:
    ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class WithPermission:
    permission: str
    service_ids: tuple[str, ...] = ()  # informational scope (e.g. affected services)
    without: str | None = None  # 027: holders of this other permission are left out (told separately)


@dataclass(frozen=True, slots=True)
class Role:
    role: str


@dataclass(frozen=True, slots=True)
class AllAuthenticated:
    pass


AudienceSpec = Users | WithPermission | Role | AllAuthenticated


@dataclass(frozen=True, slots=True)
class CommunicationRequest:
    category: str
    template_key: str  # catalog key ``namespace:key`` rendered per recipient (026)
    audience: AudienceSpec
    dedup_key: str
    kind: Kind = "notification"
    priority: Priority = "normal"
    params: Mapping[str, Any] = field(default_factory=dict)  # reference ids / short values, never secrets
    source: Source = "module"
    source_ref: str | None = None
    subject_ref: str | None = None  # opaque (``incident:<id>``…) — coalescing key
    required_permission: str | None = None  # re-checked per recipient at delivery
    valid_until: datetime | None = None
    action_url: str | None = None  # in-portal route
    # 027: the e-mail itself when it is more than the rendered template (a newsletter): {"subject",
    # "text", "html"} — sent as is, never folded into a digest
    email_body: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class CommunicationRef:
    id: UUID
    created: bool  # False: duplicate ``(source, dedup_key)``
    recipients: int = 0


@runtime_checkable
class Notifications(Protocol):
    async def send(
        self, request: CommunicationRequest, *, caller: Principal | None = None
    ) -> CommunicationRef: ...


@dataclass(frozen=True, slots=True)
class CategoryDef:
    key: str
    owner: str
    label_key: str
    default_priority: Priority = "normal"
    default_channels: tuple[str, ...] = ("portal",)
    mandatory_channels: tuple[str, ...] = ()
    user_mutable: bool = True
    # issue 258: repeats that come in series (a reward every quarter of an hour) merge into one item over this
    # many seconds since the last, while it is unread (0: the portal's coalescing window only)
    series_s: int = 0


class CategoryError(ValueError):
    pass


class CategoryRegistry:
    """Owner-tagged category declarations (F20)."""

    def __init__(self) -> None:
        self._categories: dict[str, CategoryDef] = {}

    def declare(self, category: CategoryDef) -> CategoryDef:
        if not category.key or "." not in category.key or len(category.key) > 96:
            raise CategoryError(f"invalid category key {category.key!r}")
        plugin = category.owner.startswith("plugin:")
        if plugin and not category.key.startswith(f"{category.owner}."):
            raise CategoryError(f"plugin categories are namespaced '{category.owner}.' ({category.key!r})")
        if plugin and category.mandatory_channels:
            raise CategoryError("plugin categories are never mandatory")
        if category.default_priority not in PRIORITIES:
            raise CategoryError(f"unknown priority {category.default_priority!r}")
        unknown = set(category.default_channels) | set(category.mandatory_channels)
        if unknown - set(CHANNELS):
            raise CategoryError(f"unknown channels {sorted(unknown - set(CHANNELS))}")
        existing = self._categories.get(category.key)
        if existing is not None and existing.owner != category.owner:
            raise CategoryError(f"category {category.key!r} is already declared by {existing.owner}")
        self._categories[category.key] = category
        return category

    def get(self, key: str) -> CategoryDef | None:
        return self._categories.get(key)

    def all(self) -> list[CategoryDef]:
        return [self._categories[key] for key in sorted(self._categories)]

    def unregister(self, owner: str) -> int:
        doomed = [key for key, item in self._categories.items() if item.owner == owner]
        for key in doomed:
            del self._categories[key]
        return len(doomed)


default_categories = CategoryRegistry()


def declare_category(
    key: str,
    owner: str,
    label_key: str,
    *,
    default_priority: Priority = "normal",
    default_channels: Sequence[str] = ("portal",),
    mandatory_channels: Sequence[str] = (),
    user_mutable: bool = True,
    series_s: int = 0,
    registry: CategoryRegistry | None = None,
) -> CategoryDef:
    return (registry or default_categories).declare(
        CategoryDef(
            key,
            owner,
            label_key,
            default_priority,
            tuple(default_channels),
            tuple(mandatory_channels),
            user_mutable,
            series_s,
        )
    )


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None


@runtime_checkable
class EmailTransport(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


NOTIFY_SPEC = CapabilitySpec(
    name=NOTIFY,
    version="2.0",
    protocol=Notifications,
    multi_provider=False,
    description="Produce communications (notifications, alerts) for an audience (Notifications 010).",
)
SPECS: tuple[CapabilitySpec, ...] = (NOTIFY_SPEC,)
