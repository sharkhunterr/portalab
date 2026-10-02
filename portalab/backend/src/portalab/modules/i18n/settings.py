"""i18n settings (T003, T025) declared to Administration (CD-011). Read by 020's port adapters
(``I18nPolicyReader``, ``UserLocalePreferenceReader``). User keys are personal *preference* data, erased and
exported by 020's preference participants (021)."""

from typing import Annotated, Any, Literal

from pydantic import Field

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:i18n"
Code = Annotated[str, Field(pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")]

GLOBAL: tuple[tuple[str, Any, Any, str], ...] = (
    ("i18n.defaultLanguage", Code, "en", "Portal default interface language."),
    ("i18n.enabledLanguages", list[Code], ["en", "fr"], "Languages users may choose."),
    ("i18n.fallbackChain", list[Code], ["en"], "Languages tried, in order, when a translation is missing."),
    ("i18n.defaultLocale", Code, "en", "Default formatting locale (dates, numbers)."),
    ("i18n.defaultTimeZone", str, "UTC", "Default time zone (IANA name)."),
    (
        "i18n.unknownLanguagePolicy",
        Literal["show_as_is", "hide"],
        "show_as_is",
        "Content with no declared language.",
    ),
    (
        "i18n.ambiguousTimePolicy",
        Literal["gap_forward|overlap_earlier", "gap_forward|overlap_later", "gap_backward|overlap_earlier"],
        "gap_forward|overlap_earlier",
        "How wall-clock times inside DST gaps/overlaps resolve.",
    ),
    ("i18n.schedulingDefault", Literal["absolute", "wall_clock"], "absolute", "Default scheduling mode."),
)
USER: tuple[tuple[str, Any, Any, str], ...] = (
    ("i18n.language", Code | None, None, "Your interface language."),
    ("i18n.locale", Code | None, None, "Your formatting locale (dates, numbers)."),
    ("i18n.timeZone", str | None, None, "Your time zone."),
    ("i18n.hourCycle", Literal["h12", "h23"] | None, None, "12- or 24-hour clock."),
    (
        "i18n.firstDayOfWeek",
        Annotated[int, Field(ge=0, le=6)] | None,
        None,
        "First day of the week (0 = Monday).",
    ),
)


def declare_i18n_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    for key, schema, default, description in GLOBAL:
        if key not in known:
            declare(
                scope="global", key=key, schema=schema, default=default, owner=OWNER, description=description
            )
    for key, schema, default, description in USER:
        if key not in known:
            declare(
                scope="global",
                key=key,
                schema=schema,
                default=default,
                user_overridable=True,
                owner=OWNER,
                description=description,
            )


declare_i18n_settings()
