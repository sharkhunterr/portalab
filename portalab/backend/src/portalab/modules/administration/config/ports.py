"""Read-port adapters (T016): ``admin.config`` (``ConfigReader``) is the ConfigService itself; the i18n ports
of spec 026 read ``i18n.*`` keys and fall back to the hard defaults while 026 has not declared them."""

from dataclasses import asdict
from typing import Any
from uuid import UUID

from portalab.capabilities.config import I18nPolicy, UserLocalePreference
from portalab.modules.administration.config.registry import UnknownSetting
from portalab.modules.administration.config.service import ConfigService

USER_KEYS = {
    "language": "i18n.language",
    "locale": "i18n.locale",
    "time_zone": "i18n.timeZone",
    "hour_cycle": "i18n.hourCycle",
    "first_day_of_week": "i18n.firstDayOfWeek",
}
POLICY_KEYS = {
    "default_language": "i18n.defaultLanguage",
    "enabled_languages": "i18n.enabledLanguages",
    "fallback_chain": "i18n.fallbackChain",
    "default_locale": "i18n.defaultLocale",
    "default_time_zone": "i18n.defaultTimeZone",
    "unknown_language_policy": "i18n.unknownLanguagePolicy",
    "ambiguous_time_policy": "i18n.ambiguousTimePolicy",
    "scheduling_default": "i18n.schedulingDefault",
}


async def _value(config: ConfigService, key: str, user_id: UUID | None = None) -> Any:
    try:
        return (await config.get(key, user_id=user_id)).value
    except UnknownSetting:
        return None


class ConfigUserLocalePreferenceReader:
    def __init__(self, config: ConfigService) -> None:
        self.config = config

    async def get(self, user_id: UUID) -> UserLocalePreference:
        values = {field: await _value(self.config, key, user_id) for field, key in USER_KEYS.items()}
        return UserLocalePreference(**values)


class ConfigI18nPolicyReader:
    def __init__(self, config: ConfigService) -> None:
        self.config = config

    async def get(self) -> I18nPolicy:
        defaults = I18nPolicy()
        values: dict[str, Any] = {}
        for field, key in POLICY_KEYS.items():
            value = await _value(self.config, key)
            if value is None:
                continue
            values[field] = tuple(value) if isinstance(value, list) else value
        return I18nPolicy(**{**asdict(defaults), **values})
