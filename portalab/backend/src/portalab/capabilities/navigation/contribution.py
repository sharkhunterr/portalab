"""``NavigationContribution`` (spec 004 T006; R2, data-model): a closed, validated declaration of a
navigation entry, command, contextual link or breadcrumb parent. Unknown fields, a missing permission or a
key outside the owner's namespace are rejected. Plugins may only enrich an existing entry through
``target_entry_key`` (the target must expose an extension slot — checked by 023)."""

from collections.abc import Callable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION: Literal[1] = 1
Kind = Literal["entry", "command", "related_link", "crumb_parent"]


class VisibleWhen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    module: str | None = Field(default=None, max_length=64)
    plugin: str | None = Field(default=None, max_length=64)
    setting: str | None = Field(default=None, max_length=128)  # a boolean configuration key


class NavigationContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_-]*(\.[a-z0-9_-]+)+$", max_length=128)
    owner: str = Field(pattern=r"^(module|plugin):[a-z0-9][a-z0-9_-]{0,63}$")
    kind: Kind
    label_key: str = Field(min_length=1, max_length=128)
    icon: str | None = Field(default=None, max_length=64)
    route: str | None = Field(default=None, pattern=r"^/[A-Za-z0-9/_:.\-]*$", max_length=256)
    action_id: str | None = Field(default=None, max_length=128)
    group: str = Field(default="main", pattern=r"^[a-z][a-z0-9_-]{0,47}$")
    order_hint: int = Field(default=100, ge=0, le=10_000)
    required_permission: str = Field(min_length=3, max_length=128)
    resource_kind: str | None = Field(default=None, max_length=64)
    existence_sensitive: bool = False
    visible_when: VisibleWhen | None = None
    target_entry_key: str | None = Field(default=None, max_length=128)  # related_link/crumb_parent anchor
    keywords: tuple[str, ...] = ()
    sensitivity: Literal["normal", "sensitive"] = "normal"  # commands (008 F17)
    confirmation_required: bool = False
    schema_version: Literal[1] = SCHEMA_VERSION

    @model_validator(mode="after")
    def _shape(self) -> "NavigationContribution":
        owner_kind, owner_id = self.owner.split(":", 1)
        prefix = f"plugin.{owner_id}." if owner_kind == "plugin" else f"{owner_id}."
        if not self.key.startswith(prefix):
            raise ValueError(f"key must be namespaced under {prefix!r}")
        if self.kind in ("entry", "related_link") and not self.route:
            raise ValueError(f"a {self.kind} needs a route")
        if self.kind == "command" and not (self.route or self.action_id):
            raise ValueError("a command needs a route or an action_id")
        if self.kind in ("related_link", "crumb_parent") and not self.target_entry_key:
            raise ValueError(f"a {self.kind} needs a target_entry_key")
        return self


Upgrader = Callable[[dict[str, Any]], dict[str, Any]]
_UPGRADERS: dict[int, Upgrader] = {}


def register_upgrader(from_version: int, upgrade: Upgrader) -> None:
    """Hook for future schema versions: upgrade a raw declaration from ``from_version`` to the next."""
    _UPGRADERS[from_version] = upgrade


def upgrade_raw(raw: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(raw)
    version = int(data.get("schema_version", SCHEMA_VERSION))
    while version < SCHEMA_VERSION:
        data = _UPGRADERS[version](data)
        version += 1
        data["schema_version"] = version
    return data
