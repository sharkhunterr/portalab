"""``LocaleResolver`` (T012; R8, FR-001..007): deterministic, side-effect free.

Language: the user's preference if it is enabled, else the portal default if enabled, else ``en`` (hard
default). Locale and time zone are resolved **independently** of the language (preference → portal
default → ``en`` / ``UTC``; an unknown time zone falls back to the default). A preference hidden by policy
is kept (``retained_language``) and applies again as soon as its language is re-enabled. Results are cached
per ``(user, locale_epoch)``; the epoch is bumped when i18n settings change.
"""

from collections import OrderedDict
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portalab.capabilities.config import I18N_POLICY_READER, LOCALE_READER, I18nPolicy, UserLocalePreference
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilityRegistry

HARD_LANGUAGE = "en"
HARD_TIME_ZONE = "UTC"
RTL = frozenset({"ar", "he", "fa", "ur", "ps", "yi", "dv", "ku", "sd", "ug"})


def valid_time_zone(name: str | None) -> bool:
    if not name:
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def resolve(preference: UserLocalePreference, policy: I18nPolicy) -> LocaleContext:
    enabled = list(policy.enabled_languages)
    if preference.language and preference.language in enabled:
        language, retained = preference.language, None
    else:
        language = policy.default_language if policy.default_language in enabled else HARD_LANGUAGE
        retained = preference.language if preference.language and preference.language != language else None
    locale = preference.locale or policy.default_locale or language
    candidates = (preference.time_zone, policy.default_time_zone, HARD_TIME_ZONE)
    time_zone = next((tz for tz in candidates if tz and valid_time_zone(tz)), HARD_TIME_ZONE)
    chain = tuple(dict.fromkeys(code for code in (*policy.fallback_chain, HARD_LANGUAGE) if code != language))
    hour_cycle = preference.hour_cycle if preference.hour_cycle in ("h12", "h23") else None
    return LocaleContext(
        language=language,
        locale=locale,
        time_zone=time_zone,
        direction="rtl" if language.split("-")[0] in RTL else "ltr",
        fallback_chain=chain,
        hour_cycle=hour_cycle,  # type: ignore[arg-type]
        first_day_of_week=preference.first_day_of_week,
        retained_language=retained,
    )


class LocaleResolver:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities
        self.epoch = 0
        self._cache: OrderedDict[tuple[Any, int], LocaleContext] = OrderedDict()

    def _port(self, name: str) -> Any:
        providers = self.capabilities.system_providers(name)
        return providers[0].provider if providers else None

    def bump(self) -> int:
        self.epoch += 1
        self._cache.clear()
        return self.epoch

    async def policy(self) -> I18nPolicy:
        port = self._port(I18N_POLICY_READER)
        try:
            return await port.get() if port else I18nPolicy()
        except Exception:
            return I18nPolicy()

    async def for_user(self, user_id: UUID | None) -> LocaleContext:
        key = (user_id, self.epoch)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        reader = self._port(LOCALE_READER)
        preference = UserLocalePreference()
        if user_id is not None and reader is not None:
            try:
                preference = await reader.get(user_id)
            except Exception:
                preference = UserLocalePreference()
        context = resolve(preference, await self.policy())
        self._cache[key] = context
        if len(self._cache) > 2048:
            self._cache.popitem(last=False)
        return context
