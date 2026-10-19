"""The site's own words in the catalogs (issue 159): « Portalab » becomes the site's name and « Coins » its
currency, in every message of every process (the pages, the e-mails, the notifications) — the catalogs are
rewritten once per version of the site's identity, never message by message.

A number written just before the currency (``{price} Coins``) chooses the singular or the plural by the
language's plural rules (ICU: ``{price} {price, plural, one {Xenocoin} other {Xenocoins}}``); elsewhere the
plural is used (« Your Coins »), and an existing plural branch keeps its own form (``one {# Coin}``).
The administration's technical texts keep « Portalab »: they name the software, not the site."""

import re
from functools import lru_cache

from portalab.capabilities.i18n import SiteTerms

TECHNICAL_NAMESPACES = frozenset({"admin", "plugins"})  # the software's name, for its administrators
# the page that sets the site's words names Portalab's own (« Empty: “Coins” »): never rewritten
UNTOUCHED = ("admin", "site.")
BRAND = re.compile(r"\bPortalab\b")
COUNTED = re.compile(r"\{(\w+)(?:, ?number)?\} Coins\b")
PLURAL = re.compile(r"\bCoins\b")
SINGULAR = re.compile(r"\bCoin\b")


def technical(namespace: str, key: str) -> bool:
    return namespace in TECHNICAL_NAMESPACES or key.startswith("admin.")


def _quoted(word: str | None) -> str | None:
    """An apostrophe is ICU's quote: doubled, it is an apostrophe (« L'Antre » → ``L''Antre``)."""
    return word.replace("'", "''") if word else None


@lru_cache(maxsize=32768)  # each message once per version of the site's words
def rewrite(namespace: str, key: str, message: str, terms: SiteTerms) -> str:
    if terms.empty or (namespace == UNTOUCHED[0] and key.startswith(UNTOUCHED[1])):
        return message
    other = _quoted(terms.currency_other or terms.currency_one)
    one = _quoted(terms.currency_one) or other
    if other and one:
        counted: list[str] = []  # set aside, so a name holding « Coins » itself is not rewritten twice

        def count(match: re.Match[str]) -> str:
            counted.append(f"{{{match[1]}}} {{{match[1]}, plural, one {{{one}}} other {{{other}}}}}")
            return f"\x00{len(counted) - 1}\x00"

        if one != other:
            message = COUNTED.sub(count, message)
        message = SINGULAR.sub(lambda _: one, PLURAL.sub(lambda _: other, message))
        for index, text in enumerate(counted):
            message = message.replace(f"\x00{index}\x00", text)
    name = _quoted(terms.name)
    if name and not technical(namespace, key):
        message = BRAND.sub(lambda _: name, message)
    return message


def rewrite_all(namespace: str, messages: dict[str, str], terms: SiteTerms) -> dict[str, str]:
    if terms.empty:
        return messages
    return {key: rewrite(namespace, key, message, terms) for key, message in messages.items()}
