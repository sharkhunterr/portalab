"""Configuration read contracts (spec 020, CD-011) — consumed by every module, implemented by Administration.

* ``admin.config`` — ``ConfigReader.get(key, user_id=None, module=None, plugin=None) -> EffectiveValue``;
* ``UserLocalePreferenceReader`` / ``I18nPolicyReader`` — read ports of spec 026, implemented by 020;
* ``SettingUpgrade`` — stored-value migrations registered next to the declarations.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "admin.config"
LOCALE_READER = "admin.user_locale_preference"
I18N_POLICY_READER = "admin.i18n_policy"

SourceScope = Literal["default", "global", "module", "plugin", "user"]


@dataclass(frozen=True, slots=True)
class EffectiveValue:
    key: str
    value: Any
    source: SourceScope
    locked: bool = False
    user_value_retained: bool = False  # the user's own value exists but a policy currently overrides it


@runtime_checkable
class ConfigReader(Protocol):
    async def get(
        self, key: str, *, user_id: UUID | None = None, module: str | None = None, plugin: str | None = None
    ) -> EffectiveValue: ...


@dataclass(frozen=True, slots=True)
class UserLocalePreference:
    language: str | None = None
    locale: str | None = None
    time_zone: str | None = None
    hour_cycle: str | None = None
    first_day_of_week: int | None = None


@dataclass(frozen=True, slots=True)
class I18nPolicy:
    default_language: str = "en"
    enabled_languages: tuple[str, ...] = ("en", "fr")
    fallback_chain: tuple[str, ...] = ("en",)
    default_locale: str = "en"
    default_time_zone: str = "UTC"
    unknown_language_policy: str = "show_as_is"
    ambiguous_time_policy: str = "gap_forward|overlap_earlier"
    scheduling_default: str = "absolute"


@runtime_checkable
class UserLocalePreferenceReader(Protocol):
    async def get(self, user_id: UUID) -> UserLocalePreference: ...


@runtime_checkable
class I18nPolicyReader(Protocol):
    async def get(self) -> I18nPolicy: ...


@dataclass(frozen=True, slots=True)
class SettingUpgrade:
    """Turns a stored value of ``from_version`` into the shape of ``from_version + 1``."""

    key: str
    from_version: int
    upgrade: Callable[[Any], Any] = field(compare=False)


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=ConfigReader,
    multi_provider=False,
    description="Effective configuration values (Global ▸ Module ▸ Plugin ▸ User within policy).",
)
LOCALE_SPEC = CapabilitySpec(
    name=LOCALE_READER,
    version="1.0",
    protocol=UserLocalePreferenceReader,
    multi_provider=False,
    description="A user's language/locale/time-zone preferences (port of spec 026).",
)
I18N_SPEC = CapabilitySpec(
    name=I18N_POLICY_READER,
    version="1.0",
    protocol=I18nPolicyReader,
    multi_provider=False,
    description="Portal language policy (port of spec 026).",
)
