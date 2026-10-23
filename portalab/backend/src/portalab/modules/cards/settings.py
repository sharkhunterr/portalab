"""Cards settings (issue 229), declared to Administration."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:cards"


@dataclass(frozen=True, slots=True)
class CardsConfig:
    face_check: bool = True
    video_frames: bool = True
    web_search: bool = False
    cutouts: bool = True


SETTINGS = {
    "face_check": "cards.faceCheck",
    "video_frames": "cards.videoFrames",
    "web_search": "cards.webSearch",
    "cutouts": "cards.cutouts",
}
_DESCRIPTIONS = {
    "face_check": (
        "An actor's character found on the web is kept only with the actor's own face (compared with their "
        "portrait, on the processor). Off: the image's page must name the character. Animated works are "
        "never compared."
    ),
    "video_frames": (
        "An actor's character is looked for in the film itself first: still images of its file, taken by the "
        "media server (Plex), where the actor's face is compared with their portrait. Off: the web only."
    ),
    "web_search": (
        "Last resort for an actor's character: images found on the web (a self-hosted SearXNG). Off (the "
        "default): a character without an image of its own shows the work's poster and the actor's portrait."
    ),
    "cutouts": (
        "The characters are cut out of their images (their background removed on the processor) and shown "
        "over a scene of the card's own: the genre's light, the work's backdrop on the borderless version. "
        "Off: the photographs as they are."
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
