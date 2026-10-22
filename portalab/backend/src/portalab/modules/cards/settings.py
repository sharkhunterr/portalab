"""Cards settings (issue 229), declared to Administration."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:cards"


@dataclass(frozen=True, slots=True)
class CardsConfig:
    face_check: bool = True


SETTINGS = {"face_check": "cards.faceCheck"}
_DESCRIPTIONS = {
    "face_check": (
        "An actor's character found on the web is kept only with the actor's own face (compared with their "
        "portrait, on the processor). Off: the image's page must name the character. Animated works are "
        "never compared."
    ),
}


def declare_cards_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = CardsConfig()
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            declare(
                scope="global",
                key=key,
                schema=type(default),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_cards_settings()
