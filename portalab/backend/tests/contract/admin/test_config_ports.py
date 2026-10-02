"""020 T016 — read ports: ``admin.config`` (ConfigReader) and the spec 026 i18n ports implemented here,
read against the settings 026 declares."""

import pytest

from portalab.capabilities.config import (
    CAPABILITY,
    I18N_POLICY_READER,
    LOCALE_READER,
    ConfigReader,
    I18nPolicyReader,
    UserLocalePreferenceReader,
)
from portalab.core.authz_port import Principal
from tests.authz_fixtures import insert_user
from tests.privacy_fixtures import FullPlatform

pytestmark = pytest.mark.integration


async def test_ports(full: FullPlatform) -> None:
    caps = full.identity.capabilities
    reader = caps.system_providers(CAPABILITY)[0].provider
    locale = caps.system_providers(LOCALE_READER)[0].provider
    policy = caps.system_providers(I18N_POLICY_READER)[0].provider
    assert isinstance(reader, ConfigReader)
    assert isinstance(locale, UserLocalePreferenceReader) and isinstance(policy, I18nPolicyReader)
    import portalab.modules.i18n.settings  # noqa: F401  (026 declares the i18n.* settings)

    user = await insert_user(full.database)
    assert (await locale.get(user)).language is None  # no preference yet
    assert (await policy.get()).enabled_languages == ("en", "fr")
    await full.administration.config.set(
        "i18n.language", "fr", scope="user", scope_ref=str(user), actor=Principal(user_id=user)
    )
    assert (await locale.get(user)).language == "fr"
    assert (await reader.get("i18n.language", user_id=user)).value == "fr"
