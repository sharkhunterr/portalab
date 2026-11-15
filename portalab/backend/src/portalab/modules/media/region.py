"""Issue 438: the portal's system language — a language and a country (« fr-FR »), set by its administrator
apart from the interface's. Metadata is fetched in it, and a title's age rating is its country's."""

from typing import Any

from babel.core import get_global

from portalab.capabilities.config import CAPABILITY as CONFIG

SYSTEM_LANGUAGE = "i18n.systemLanguage"
# before 438: the formatting locale, then the interface's language
FALLBACKS = (SYSTEM_LANGUAGE, "i18n.defaultLocale", "i18n.defaultLanguage")


async def system_language(capabilities: Any) -> str:
    """The system language (« fr-FR »), else the portal's formatting locale or its interface language —
    the ones its administrator chose first (a portal set up in French before 438 rates as France does)."""
    try:
        providers = capabilities.system_providers(CONFIG)
    except Exception:
        return "en"
    if not providers:
        return "en"
    fallback = "en"
    for key in FALLBACKS:
        try:
            found = await providers[0].provider.get(key)
        except Exception:  # noqa: S112 — undeclared (tests, an older portal): the next one
            continue
        if not found.value:
            continue
        if found.source != "default":  # one its administrator chose, before a factory value
            return str(found.value)
        fallback = fallback if fallback != "en" else str(found.value)
    return fallback


def country_of(tag: str | None) -> str | None:
    """The country of a language tag (« fr-FR » → « FR »), else its language's likeliest (« fr » → « FR »,
    « en » → « US »); ``None`` when unknown."""
    parts = (tag or "").replace("_", "-").split("-")
    for part in parts[1:]:
        if len(part) == 2 and part.isalpha():
            return part.upper()
    language = parts[0].lower()
    if not language.isalpha():
        return None
    likely = str(get_global("likely_subtags").get(language) or "")
    country = likely.split("_")[-1] if likely.count("_") >= 1 else ""
    return country.upper() if len(country) == 2 and country.isalpha() else None
