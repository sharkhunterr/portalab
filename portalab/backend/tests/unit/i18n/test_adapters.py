"""026 T033 — search normalization; response language with fallback; recipient locale (not sender)."""

from uuid import UUID, uuid4

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.config import I18N_POLICY_READER, LOCALE_READER, I18nPolicy, UserLocalePreference
from portalab.capabilities.i18n import normalize_for_search
from portalab.modules.i18n.adapters.locale_for_user import RecipientLocale, ResponseLanguage
from portalab.modules.i18n.resolver.resolver import LocaleResolver


def test_normalize_for_search() -> None:
    assert normalize_for_search("Éléphant ROSE") == normalize_for_search("elephant rose") == "elephant rose"
    assert normalize_for_search("Straße") == "strasse"
    assert normalize_for_search("ﬁlm") == "film"  # NFKC ligature
    assert normalize_for_search("İSTANBUL", "tr").startswith("istanbul")


class Prefs:
    def __init__(self, table: dict[UUID, UserLocalePreference]) -> None:
        self.table = table

    async def get(self, user_id: UUID) -> UserLocalePreference:
        return self.table.get(user_id, UserLocalePreference())


class Policy:
    async def get(self) -> I18nPolicy:
        return I18nPolicy(enabled_languages=("en", "fr", "de"), fallback_chain=("fr", "en"))


async def test_recipient_and_response_language() -> None:
    sender, recipient = uuid4(), uuid4()
    capabilities = new_registry()
    capabilities.provide(
        LOCALE_READER,
        Prefs(
            {
                sender: UserLocalePreference(language="en"),
                recipient: UserLocalePreference(language="de", time_zone="Europe/Berlin"),
            }
        ),
        instance_ref="t",
        owner="t",
    )
    capabilities.provide(I18N_POLICY_READER, Policy(), instance_ref="t", owner="t")
    resolver = LocaleResolver(capabilities)
    ctx = await RecipientLocale(resolver).for_user(recipient)
    assert (ctx.language, ctx.time_zone) == ("de", "Europe/Berlin")
    assert (
        await ResponseLanguage(resolver).for_user(recipient, supported=["en", "fr"]) == "fr"
    )  # model lacks de
    assert await ResponseLanguage(resolver).for_user(recipient) == "de"
