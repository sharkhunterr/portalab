"""026 T011 — resolution matrix: preference enabled/disabled/absent/unknown; hard default; language,
locale and time zone independent; preference retained and restored; deterministic."""

from portalab.capabilities.config import I18nPolicy, UserLocalePreference
from portalab.modules.i18n.resolver.resolver import resolve

POLICY = I18nPolicy(
    default_language="en",
    enabled_languages=("en", "fr"),
    fallback_chain=("en",),
    default_locale="en",
    default_time_zone="Europe/Paris",
)


def test_matrix() -> None:
    assert resolve(UserLocalePreference(language="fr"), POLICY).language == "fr"
    disabled = resolve(UserLocalePreference(language="de"), POLICY)
    assert disabled.language == "en" and disabled.retained_language == "de"
    assert resolve(UserLocalePreference(), POLICY).language == "en"
    assert resolve(UserLocalePreference(language="xx"), POLICY).language == "en"
    no_default = I18nPolicy(default_language="de", enabled_languages=("fr",))
    assert resolve(UserLocalePreference(), no_default).language == "en"  # hard default


def test_independent_axes_and_restore() -> None:
    ctx = resolve(UserLocalePreference(language="en", locale="de-DE", time_zone="America/New_York"), POLICY)
    assert (ctx.language, ctx.locale, ctx.time_zone) == ("en", "de-DE", "America/New_York")
    assert resolve(UserLocalePreference(time_zone="Mars/Olympus"), POLICY).time_zone == "Europe/Paris"
    hidden = resolve(UserLocalePreference(language="de"), POLICY)
    restored = resolve(UserLocalePreference(language="de"), I18nPolicy(enabled_languages=("en", "fr", "de")))
    assert hidden.language == "en" and restored.language == "de" and restored.retained_language is None


def test_deterministic_and_direction() -> None:
    pref = UserLocalePreference(language="ar", hour_cycle="h23", first_day_of_week=6)
    policy = I18nPolicy(enabled_languages=("en", "ar"))
    assert resolve(pref, policy) == resolve(pref, policy)
    ctx = resolve(pref, policy)
    assert ctx.direction == "rtl" and ctx.hour_cycle == "h23" and ctx.first_day_of_week == 6
    assert ctx.fallback_chain == ("en",)
