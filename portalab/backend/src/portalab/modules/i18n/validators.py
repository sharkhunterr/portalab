"""Setting validators (T025): BCP-47 codes known to the portal, enabled ⊇ default, an acyclic fallback
chain (no duplicates, known codes), valid IANA time zones and CLDR locales. Registered as dynamic
validators with Administration's setting registry at wiring time."""

from collections.abc import Awaitable, Callable
from typing import Any

from babel import Locale, UnknownLocaleError
from sqlalchemy import select

from portalab.capabilities.config import I18nPolicy
from portalab.core.db import Database
from portalab.modules.i18n.models import Language
from portalab.modules.i18n.resolver.resolver import valid_time_zone

Validator = Callable[[Any], Awaitable[list[str]]]


class I18nValidators:
    def __init__(self, database: Database, policy: Callable[[], Awaitable[I18nPolicy]]) -> None:
        self.database = database
        self.policy = policy

    async def known(self) -> set[str]:
        async with self.database.session() as session:
            return set((await session.execute(select(Language.code))).scalars())

    async def enabled_languages(self, value: Any) -> list[str]:
        codes = list(value or [])
        unknown = sorted(set(codes) - await self.known())
        problems = [f"unknown language {code!r}" for code in unknown]
        default = (await self.policy()).default_language
        if default not in codes:
            problems.append(f"the default language {default!r} must stay enabled")
        return problems

    async def default_language(self, value: Any) -> list[str]:
        if value not in await self.known():
            return [f"unknown language {value!r}"]
        if value not in (await self.policy()).enabled_languages:
            return [f"{value!r} must be enabled before it becomes the default"]
        return []

    async def fallback_chain(self, value: Any) -> list[str]:
        codes = list(value or [])
        problems = [f"unknown language {code!r}" for code in sorted(set(codes) - await self.known())]
        if len(codes) != len(set(codes)):
            problems.append("the fallback chain must not repeat a language (no cycles)")
        return problems

    async def user_language(self, value: Any) -> list[str]:
        if value is None:
            return []
        return (
            []
            if value in (await self.policy()).enabled_languages
            else [f"{value!r} is not an enabled language"]
        )

    async def time_zone(self, value: Any) -> list[str]:
        if value is None:
            return []
        return [] if valid_time_zone(str(value)) else [f"unknown time zone {value!r}"]

    async def locale(self, value: Any) -> list[str]:
        if value is None:
            return []
        try:
            Locale.parse(str(value).replace("-", "_"))
        except (UnknownLocaleError, ValueError):
            return [f"unknown locale {value!r}"]
        return []

    def table(self) -> dict[str, Validator]:
        return {
            "i18n.enabledLanguages": self.enabled_languages,
            "i18n.defaultLanguage": self.default_language,
            "i18n.fallbackChain": self.fallback_chain,
            "i18n.defaultTimeZone": self.time_zone,
            "i18n.timeZone": self.time_zone,
            "i18n.defaultLocale": self.locale,
            "i18n.locale": self.locale,
            "i18n.language": self.user_language,
        }
