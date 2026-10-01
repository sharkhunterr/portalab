"""T046 — declare_setting contract (contracts/bootstrap-settings.md, CD-011). Declaration only, no store."""

import pytest

from portalab.core.config_declaration import SCOPES, SettingCatalog, SettingDeclarationError

pytestmark = pytest.mark.unit


def test_scopes_follow_the_configuration_hierarchy() -> None:
    assert SCOPES == ("global", "module", "plugin", "user")


def test_valid_declaration_is_enumerable() -> None:
    catalog = SettingCatalog()
    decl = catalog.declare(
        scope="global",
        key="i18n.defaultLanguage",
        schema=str,
        default="en",
        description="Portal default language",
    )
    assert decl.version == 1
    assert decl.sensitive is False
    assert catalog.get("i18n.defaultLanguage") is decl
    assert [d.key for d in catalog.all()] == ["i18n.defaultLanguage"]
    assert catalog.validate("i18n.defaultLanguage", "fr") == "fr"


def test_default_must_match_schema() -> None:
    catalog = SettingCatalog()
    with pytest.raises(SettingDeclarationError):
        catalog.declare(scope="global", key="jobs.retentionDays", schema=int, default="thirty")


def test_values_are_validated_against_schema() -> None:
    catalog = SettingCatalog()
    catalog.declare(scope="global", key="jobs.retentionDays", schema=int, default=30)
    assert catalog.validate("jobs.retentionDays", "45") == 45
    with pytest.raises(SettingDeclarationError):
        catalog.validate("jobs.retentionDays", "many")


def test_duplicate_key_is_rejected() -> None:
    catalog = SettingCatalog()
    catalog.declare(scope="global", key="demo.flag", schema=bool, default=False)
    with pytest.raises(SettingDeclarationError):
        catalog.declare(scope="module", key="demo.flag", schema=bool, default=True)


@pytest.mark.parametrize("key", ["flag", "Demo.flag", "demo.", ".flag", "demo flag", "demo..flag"])
def test_key_format_is_module_dot_name(key: str) -> None:
    with pytest.raises(SettingDeclarationError):
        SettingCatalog().declare(scope="global", key=key, schema=bool, default=False)


def test_unknown_scope_is_rejected() -> None:
    with pytest.raises(SettingDeclarationError):
        SettingCatalog().declare(scope="tenant", key="demo.flag", schema=bool, default=False)  # type: ignore[arg-type]


def test_sensitive_settings_cannot_have_a_default_and_are_flagged() -> None:
    catalog = SettingCatalog()
    with pytest.raises(SettingDeclarationError):
        catalog.declare(
            scope="global", key="notifications.smtpPassword", schema=str, default="changeme", sensitive=True
        )
    decl = catalog.declare(
        scope="global", key="notifications.smtpPassword", schema=str, default=None, sensitive=True
    )
    assert decl.sensitive is True
    assert "changeme" not in repr(decl)


def test_user_overridable_only_for_non_sensitive_settings() -> None:
    catalog = SettingCatalog()
    with pytest.raises(SettingDeclarationError):
        catalog.declare(
            scope="user",
            key="demo.secretPref",
            schema=str,
            default=None,
            sensitive=True,
            user_overridable=True,
        )
    decl = catalog.declare(
        scope="user", key="ui.density", schema=str, default="comfortable", user_overridable=True
    )
    assert decl.user_overridable is True


def test_version_must_be_positive_and_owner_unregisters() -> None:
    catalog = SettingCatalog()
    with pytest.raises(SettingDeclarationError):
        catalog.declare(scope="global", key="demo.flag", schema=bool, default=False, version=0)
    catalog.declare(
        scope="plugin", key="plugin_hello.greeting", schema=str, default="hi", owner="plugin:hello"
    )
    assert catalog.unregister("plugin:hello") == 1
    assert catalog.all() == []
