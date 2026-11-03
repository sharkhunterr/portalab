"""#347 — what a member wants on their home, said at the welcome: each taste brings its widgets (the first
ones first). A dashboard made « to taste » keeps the administrator's starter for the member's play profile,
leaves out the widgets of the tastes not chosen, and adds those of the chosen ones it lacks; a widget of no
taste (a clock, a note, the welcome) stays as the administrator put it."""

from typing import Literal

Taste = Literal["watch", "releases", "news", "requests", "play", "stats", "services", "community", "radio"]

TASTES: dict[str, tuple[str, ...]] = {
    "watch": ("media.continue", "media.for_you", "media.recently_added"),
    "releases": ("media.recent_releases", "media.next_releases", "calendar.upcoming"),
    "news": ("news.my_feed", "news.featured"),
    "requests": ("media.requests", "media.my_soon"),
    "play": (
        "gamification.progress",
        "gamification.daily_objectives",
        "gamification.daily_wheel",
        "cards.collection",
        "marketplace.reserve",
    ),
    "stats": ("media.stats", "media.top", "media.server_playing"),
    "services": ("health.services_summary", "health.service_links", "support.open_incidents"),
    "community": ("community.activity", "community.leaderboard", "community.projects"),
    "radio": ("media.radio",),
}

TASTE_OF: dict[str, str] = {key: taste for taste, keys in TASTES.items() for key in keys}


def wanted(themes: frozenset[str] | None, key: str) -> bool:
    """Whether a widget belongs on a dashboard made to these tastes (none given: every widget does)."""
    taste = TASTE_OF.get(key)
    return themes is None or taste is None or taste in themes
