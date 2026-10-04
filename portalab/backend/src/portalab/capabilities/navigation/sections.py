"""``NavigationSection`` (spec 027 R1, data-model §1): a named, iconified group of navigation entries.

Sections are declared like contributions — by modules and plugins, validated, closed — and live in the same
``NavigationRegistry`` so that withdrawing an owner removes its entries *and* its sections at once. An entry
names its section through ``group``; an unknown section falls back to the section declaring the owner in
``default_for``, else to ``more`` (never dropped). ``audience`` decides where a section renders: the main
navigation, the Administration area, or the personal (avatar) menu.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FALLBACK_SECTION = "more"
LEGACY_GROUP = "main"  # the 004 default group: silently routed to the owner default / fallback


class SectionTopic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$")
    label_key: str = Field(min_length=1, max_length=128)
    order_hint: int = Field(default=100, ge=0, le=10_000)


class NavigationSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$")
    owner: str = Field(pattern=r"^(module|plugin):[a-z0-9][a-z0-9_-]{0,63}$")
    label_key: str = Field(min_length=1, max_length=128)
    icon: str | None = Field(default=None, max_length=64)
    order_hint: int = Field(default=100, ge=0, le=10_000)
    audience: Literal["everyone", "administration", "personal"] = "everyone"
    topics: tuple[SectionTopic, ...] = ()
    default_for: tuple[str, ...] = ()  # owners whose unplaced entries land here

    @model_validator(mode="after")
    def _shape(self) -> "NavigationSection":
        kind, ident = self.owner.split(":", 1)
        if kind == "plugin" and not self.key.startswith(f"plugin-{ident}"):
            raise ValueError(f"a plugin section key must start with 'plugin-{ident}'")
        if len({t.key for t in self.topics}) != len(self.topics):
            raise ValueError("duplicate topic keys")
        return self

    def topic(self, key: str | None) -> SectionTopic | None:
        return next((t for t in self.topics if t.key == key), None) if key else None
