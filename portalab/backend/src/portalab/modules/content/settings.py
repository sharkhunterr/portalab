"""Shared content settings (T002): external images and Mermaid diagrams."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:content"


@dataclass(frozen=True, slots=True)
class ContentConfig:
    allow_external_images: bool = False
    mermaid_enabled: bool = True


SETTINGS = {
    "allow_external_images": "content.allowExternalImages",
    "mermaid_enabled": "content.mermaid.enabled",
}
_DESCRIPTIONS = {
    "allow_external_images": "Show images hosted outside the portal in news and wiki "
    "(privacy: off by default).",
    "mermaid_enabled": "Render Mermaid diagrams (strict mode) in news and wiki.",
}


def declare_content_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = ContentConfig()
    for name, key in SETTINGS.items():
        if key not in known:
            declare(
                scope="global",
                key=key,
                schema=bool,
                default=getattr(defaults, name),
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_content_settings()
