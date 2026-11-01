"""#320: what the notifications' e-mails need to wear Portalab's look — who sends (the site's name, its public
address) and the e-mails' own words, in the recipient's language."""

from collections.abc import Callable, Mapping
from typing import Any

from portalab.capabilities.i18n import RENDERER, LocaleContext
from portalab.capabilities.notifications.layout import Brand, site_brand


async def brand(provider: Callable[[str], Any | None], portal: str, language: str) -> Brand:
    return await site_brand(provider, portal, language)


def words(
    provider: Callable[[str], Any | None], key: str, ctx: LocaleContext, args: Mapping[str, Any] | None = None
) -> str:
    """``namespace:key`` in the recipient's language (the key itself when nothing renders it)."""
    namespace, _, name = key.partition(":")
    renderer = provider(RENDERER)
    return str(renderer.t(name, ctx, dict(args or {}), namespace=namespace)) if renderer else name
