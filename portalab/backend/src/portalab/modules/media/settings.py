"""Media settings (T002), declared to Administration. ``media.fieldPriority.<kind>.<field>`` is the shape
005's reconciler reads too (ordered source systems — a connector key like ``plex`` or one service's
``plex:<id>``); an empty list means "no preference"."""

from dataclasses import dataclass, field

from portalab.capabilities.media_core import BASELINE
from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:media"
PRIORITY_FIELDS = ("title", "overview", "year", "genres", "image")


def priority_key(kind: str, name: str) -> str:
    return f"media.fieldPriority.{kind}.{name}"


def threshold_key(kind: str) -> str:
    return f"media.finishedThreshold.{kind}"


@dataclass(frozen=True, slots=True)
class MediaConfig:
    poll_active_seconds: int = 15
    poll_idle_seconds: int = 60
    stale_timeout_seconds: int = 120
    progress_event_seconds: int = 60
    quota_per_period: int = 10
    quota_period: str = "week"
    match_auto_threshold: float = 0.85
    discovery_new_days: int = 30
    discovery_shelf_size: int = 20
    thresholds: dict[str, float] = field(default_factory=dict)  # per-kind overrides (0 = explicit only)
    # 027 (#2): the portal's player
    player_enabled: bool = True
    player_owner_fallback: bool = False  # members with no linked account play through the service's own
    player_max_quality: str = "original"  # the best quality members may pick (a key of QUALITIES)


SETTINGS: dict[str, str] = {
    "poll_active_seconds": "media.playback.pollActiveSeconds",
    "poll_idle_seconds": "media.playback.pollIdleSeconds",
    "stale_timeout_seconds": "media.playback.staleTimeoutSeconds",
    "progress_event_seconds": "media.playback.progressEventSeconds",
    "quota_per_period": "media.requests.quotaPerPeriod",
    "quota_period": "media.requests.period",
    "match_auto_threshold": "media.match.autoThreshold",
    "discovery_new_days": "media.discovery.newDays",
    "discovery_shelf_size": "media.discovery.shelfSize",
    "player_enabled": "media.player.enabled",
    "player_owner_fallback": "media.player.ownerFallback",
    "player_max_quality": "media.player.maxQuality",
}

_DESCRIPTIONS = {
    "poll_active_seconds": "Seconds between playback polls while something is playing.",
    "poll_idle_seconds": "Seconds between playback polls when nothing is playing.",
    "stale_timeout_seconds": "Seconds without news from a source before a session is interrupted.",
    "progress_event_seconds": "Minimum seconds between two progress events of one session.",
    "quota_per_period": "Media requests each user may make per period (before extra units).",
    "quota_period": "Request quota period: day, week or month.",
    "match_auto_threshold": "Similarity above which two objects are proposed for merging (never merged "
    "automatically).",
    "discovery_new_days": "Days an object stays on the 'new' shelf.",
    "discovery_shelf_size": "Items per discovery shelf.",
    "player_enabled": "Members may watch films and series in the portal's own player (transcoded by Plex).",
    "player_owner_fallback": "Members with no linked account on the media server watch through the "
    "server's own account (their plays are then not theirs on the server).",
    "player_max_quality": "Best quality members may pick in the player: original, 20m, 12m, 10m, 8m, 4m, "
    "3m, 2m, 1500k, 720k or 320k.",
}


def declare_media_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = MediaConfig()
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
    for kind, _, threshold in BASELINE:
        key = threshold_key(kind)
        if threshold is not None and key not in known:
            declare(
                scope="global",
                key=key,
                schema=float,
                default=threshold,
                owner=OWNER,
                description=f"Share of a {kind} after which it counts as finished.",
            )
        for name in PRIORITY_FIELDS:
            key = priority_key(kind, name)
            if key not in known:
                declare(
                    scope="global",
                    key=key,
                    schema=list[str],
                    default=[],
                    owner=OWNER,
                    description=f"Source priority for the {name} of a {kind} (first wins).",
                )


declare_media_settings()
