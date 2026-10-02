"""Adapters for consumers (T035; R13): ``RecipientLocale`` (010: render in the *recipient's* language,
locale and time zone), ``ResponseLanguage`` (018: answer in the user's language, falling back along the
chain when the model lacks it) and the search normalizer (008, re-exported from the capability)."""

from collections.abc import Iterable
from uuid import UUID

from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.modules.i18n.resolver.resolver import LocaleResolver

__all__ = ["RecipientLocale", "ResponseLanguage", "normalize_for_search"]


class RecipientLocale:
    def __init__(self, resolver: LocaleResolver) -> None:
        self.resolver = resolver

    async def for_user(self, user_id: UUID) -> LocaleContext:
        return await self.resolver.for_user(user_id)


class ResponseLanguage:
    def __init__(self, resolver: LocaleResolver) -> None:
        self.resolver = resolver

    async def for_user(self, user_id: UUID, supported: Iterable[str] | None = None) -> str:
        ctx = await self.resolver.for_user(user_id)
        if supported is None:
            return ctx.language
        available = {code.split("-")[0] for code in supported}
        for language in (ctx.language, *ctx.fallback_chain):
            if language.split("-")[0] in available:
                return language
        return next(iter(sorted(available)), ctx.language)
