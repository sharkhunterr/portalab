"""Community settings (T002), declared to Administration."""

from dataclasses import dataclass, field

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:community"
DEFAULT_FEED_TYPES = ["achievement.unlocked", "user.level_up", "quest.completed", "project.created"]


@dataclass(frozen=True, slots=True)
class CommunityConfig:
    feed_event_types: list[str] = field(default_factory=lambda: list(DEFAULT_FEED_TYPES))
    feed_retention_days: int = 180
    members_listing_default: str = "community"
    proposals_moderation: bool = True
    proposals_allowed_roles: list[str] = field(default_factory=list)  # empty: every active account
    recognition_max_per_day: int = 5
    recognition_pair_cooldown_days: int = 30
    discovery_shelf_size: int = 8


SETTINGS: dict[str, str] = {
    "feed_event_types": "community.feed.eventTypes",
    "feed_retention_days": "community.feed.retentionDays",
    "members_listing_default": "community.members.listingDefault",
    "proposals_moderation": "community.proposals.moderation",
    "proposals_allowed_roles": "community.proposals.allowedRoles",
    "recognition_max_per_day": "community.recognition.maxPerDay",
    "recognition_pair_cooldown_days": "community.recognition.pairCooldownDays",
    "discovery_shelf_size": "community.discovery.shelfSize",
}
_DESCRIPTIONS = {
    "feed_event_types": "Domain events shown in the community feed.",
    "feed_retention_days": "Days feed entries are kept.",
    "members_listing_default": "Default directory visibility of a member (public, community, private).",
    "proposals_moderation": "Proposals need a moderator's approval before they are visible.",
    "proposals_allowed_roles": "Roles allowed to propose (empty: every active account).",
    "recognition_max_per_day": "Contributions one member may recognise per day.",
    "recognition_pair_cooldown_days": "Days before the same member may recognise the same person again.",
    "discovery_shelf_size": "Items per discovery shelf.",
}


def declare_community_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = CommunityConfig()
    schemas = {"feed_event_types": list[str], "proposals_allowed_roles": list[str]}
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            declare(
                scope="global",
                key=key,
                schema=schemas.get(name, type(default)),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_community_settings()
