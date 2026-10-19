"""Issue 159 — the site's own words in the catalogs: its name instead of « Portalab », its currency instead of
« Coins », the singular or the plural chosen by the number before it; the administration's technical texts
keep « Portalab »; an empty identity changes nothing."""

from portalab.capabilities.i18n import SiteTerms
from portalab.modules.i18n.catalog.terms import rewrite
from portalab.modules.i18n.render.icu import render

XENO = SiteTerms(name="Xenoportal", currency_one="Xenocoin", currency_other="Xenocoins")


def said(
    message: str, terms: SiteTerms, locale: str = "en", namespace: str = "marketplace", **args: object
) -> str:
    return render(rewrite(namespace, "booster.balance", message, terms), args, locale)


def test_the_number_chooses_the_singular_or_the_plural() -> None:
    assert said("Spend {price} Coins?", XENO, price=1) == "Spend 1 Xenocoin?"
    assert said("Spend {price} Coins?", XENO, price=120) == "Spend 120 Xenocoins?"
    assert said("{amount} Coins réservés", XENO, "fr", amount=0) == "0 Xenocoin réservés"  # French: 0 is one
    assert said("Your Coins: {coins}", XENO, coins=5) == "Your Xenocoins: 5"  # no number before: plural
    message = "{count, plural, one {# Coin} other {# Coins}} left"
    assert said(message, XENO, count=1) == "1 Xenocoin left"
    assert said(message, XENO, count=3) == "3 Xenocoins left"
    assert said("Spend {price} Coins?", XENO, price="1 200") == "Spend 1 200 Xenocoins?"  # text: the plural


def test_the_name_and_its_quoting() -> None:
    assert said("Confirm your Portalab account", XENO) == "Confirm your Xenoportal account"
    antre = SiteTerms(name="L'Antre", currency_one="Pièce d'or", currency_other="Pièces d'or")
    assert said("Welcome to Portalab — {price} Coins", antre, price=2) == "Welcome to L'Antre — 2 Pièces d'or"
    assert said("{price} Coins", antre, price=1) == "1 Pièce d'or"
    gold = SiteTerms(currency_one="Gold Coin", currency_other="Gold Coins")  # a name holding the word itself
    assert said("{price} Coins and more Coins", gold, price=2) == "2 Gold Coins and more Gold Coins"


def test_technical_texts_and_an_empty_identity_are_left_alone() -> None:
    assert rewrite("admin", "visuals.builtin", "Portalab", XENO) == "Portalab"
    assert rewrite("marketplace", "admin.boosters.scenePortalab", "Portalab's", XENO) == "Portalab's"
    assert rewrite("admin", "x", "Price (Coins)", XENO) == "Price (Xenocoins)"  # the currency everywhere
    assert rewrite("core", "x", "Portalab · {price} Coins", SiteTerms()) == "Portalab · {price} Coins"
    assert (
        rewrite("core", "x", "Coinsurance, Portalabs", XENO) == "Coinsurance, Portalabs"
    )  # whole words only


def test_every_message_of_the_catalogs_still_parses() -> None:
    import json

    from portalab.modules.i18n.catalog.service import LOCALES_DIR
    from portalab.modules.i18n.render.icu import parse

    antre = SiteTerms(name="L'Antre", currency_one="Pièce d'or", currency_other="Pièces d'or")
    checked = 0
    for path in sorted(LOCALES_DIR.glob("*/*.json")):
        for key, message in json.loads(path.read_text(encoding="utf-8")).items():
            for terms in (XENO, antre):
                parse(rewrite(path.stem, key, message, terms))
            checked += 1
    assert checked > 1000


def test_the_identity_page_keeps_portalabs_own_words() -> None:
    message = "Empty: « Coins »."
    assert rewrite("admin", "site.currency.description", message, XENO) == message
