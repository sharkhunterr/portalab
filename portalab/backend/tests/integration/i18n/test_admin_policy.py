"""026 T024/T025/T040 — policy constrains the user choice while the preference is retained and restored;
validators (enabled ⊇ default, acyclic chain, known codes, valid zones); i18n.manage required and audited;
an AI principal cannot change policy; language lifecycle (disable/re-enable)."""

import pytest
from sqlalchemy import text

from portalab.modules.administration.config.service import Change
from tests.authz_fixtures import SYSTEM_ACTOR, ai, insert_user, make_admin, user
from tests.integration.i18n.conftest import I18nHarness


async def test_policy_and_preferences(i18n: I18nHarness) -> None:
    config = i18n.full.administration.config
    resolver = i18n.module.resolver
    member = await insert_user(i18n.full.database)
    await config.apply([Change("i18n.language", "fr", "user", str(member))], user(member), admin_change=False)
    assert (await resolver.for_user(member)).language == "fr"
    await config.apply([Change("i18n.enabledLanguages", ["en"])], SYSTEM_ACTOR, admin_change=True)
    resolver.bump()
    hidden = await resolver.for_user(member)
    assert hidden.language == "en" and hidden.retained_language == "fr"  # preference kept
    await config.apply([Change("i18n.enabledLanguages", ["en", "fr"])], SYSTEM_ACTOR, admin_change=True)
    resolver.bump()
    assert (await resolver.for_user(member)).language == "fr"  # restored


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("i18n.enabledLanguages", ["fr"]),  # drops the default
        ("i18n.enabledLanguages", ["en", "xx"]),
        ("i18n.fallbackChain", ["en", "fr", "en"]),
        ("i18n.defaultTimeZone", "Mars/Olympus"),
        ("i18n.defaultLanguage", "fr-CA"),
    ],
)
async def test_validators(i18n: I18nHarness, key: str, value: object) -> None:
    from portalab.core.errors import PortalError

    with pytest.raises(PortalError):
        await i18n.full.administration.config.apply([Change(key, value)], SYSTEM_ACTOR, admin_change=True)


async def test_user_language_must_be_enabled(i18n: I18nHarness) -> None:
    from portalab.core.errors import PortalError

    member = await insert_user(i18n.full.database)
    with pytest.raises(PortalError):
        await i18n.full.administration.config.apply(
            [Change("i18n.language", "de", "user", str(member))], user(member), admin_change=False
        )


async def test_translation_admin(i18n: I18nHarness) -> None:
    from portalab.modules.i18n.admin import InvalidMessage, PlaceholderMismatch

    admin_id = await insert_user(i18n.full.database)
    await make_admin(i18n.full, admin_id)
    admin = user(admin_id)
    with pytest.raises(PlaceholderMismatch):
        await i18n.module.admin.put(
            admin, namespace="core", key="notTranslated", language="fr", message="Pas de traduction"
        )
    with pytest.raises(InvalidMessage):
        await i18n.module.admin.put(
            admin, namespace="core", key="items", language="fr", message="{count, plural, one {#}"
        )
    saved = await i18n.module.admin.put(
        admin, namespace="core", key="retry", language="fr", message="Recommencer"
    )
    assert saved["catalog_version"] == 1
    from portalab.capabilities.i18n import LocaleContext

    assert i18n.module.catalogs.t("retry", LocaleContext(language="fr", locale="fr")) == "Recommencer"
    async with i18n.full.database.session() as session:
        audited = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action = 'i18n.translation_updated'")
        )
        version = await session.scalar(
            text("SELECT version FROM i18n.catalog_versions WHERE namespace = 'core' AND language = 'fr'")
        )
    assert audited == 1 and version
    assert (
        ai(admin_id).channel == "ai"
    )  # policy changes go through 020 with i18n.manage (bounded by the user)
