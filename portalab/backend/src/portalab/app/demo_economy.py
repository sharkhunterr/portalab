"""Economy set-up for demo and LAN deployments (027): what earns XP (each action, by count **and** time
watched), play streaks, seasonal campaigns (bonuses on genres, shop discounts) and a year of daily, weekly
and monthly quests, plus a feedback request — all idempotent (natural keys; nothing is overwritten once an
administrator changed it)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

# --- what earns XP ---------------------------------------------------------------------------------------
RULES: dict[str, dict[str, Any]] = {
    # a play counts once (10 XP) and for its length (1 XP a minute, up to 4 h): ten 5-minute episodes
    # give 150 XP, one 4-hour film 250 XP; at most 1500 XP a day from playback
    "media_playback": {
        "event_type": "media.playback_finished",
        "label": "Lecture d'un film, d'un épisode ou d'un livre audio",
        "grants": [
            {"value": "xp", "amount": 10, "per_unit": {"field": "duration_s", "factor": 1 / 60, "max": 240}},
            {"value": "coins", "amount": 2},
        ],
        "limits": {"caps": [{"period": "day", "max_amount": 1500, "value": "xp"}]},
    },
    "shop_purchase": {
        "event_type": "marketplace.purchase",
        "label": "Achat dans la boutique",
        "grants": [{"value": "xp", "amount": 15}],
        "limits": {"caps": [{"period": "day", "max_amount": 150, "value": "xp"}]},
    },
    "ticket_created": {
        "event_type": "ticket.created",
        "label": "Création d'un ticket support",
        "grants": [{"value": "xp", "amount": 10}, {"value": "contribution", "amount": 2}],
        "limits": {"cooldown_seconds": 600, "caps": [{"period": "day", "max_amount": 50, "value": "xp"}]},
    },
    "feedback_request": {
        "event_type": "feedback.submitted",
        "label": "Réponse à une demande d'avis",
        "predicate": [{"field": "target", "op": "eq", "value": "request"}],
        "grants": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
    },
    "feedback_given": {
        "event_type": "feedback.submitted",
        "label": "Avis envoyé",
        "predicate": [{"field": "target", "op": "eq", "value": "submitted"}],
        "grants": [{"value": "xp", "amount": 10}, {"value": "contribution", "amount": 1}],
        "limits": {"cooldown_seconds": 3600, "caps": [{"period": "day", "max_amount": 30, "value": "xp"}]},
    },
    "media_request": {
        "event_type": "media.request_created",
        "label": "Demande d'un film ou d'une série",
        "grants": [{"value": "xp", "amount": 5}],
        "limits": {"caps": [{"period": "day", "max_amount": 25, "value": "xp"}]},
    },
}

# play streaks: x1.5 from 2 days in a row, x2 from 5, x2.5 from 10 — on XP and Coins of plays
STREAK: dict[str, Any] = {
    "enabled": True,
    "event_types": ["media.playback_finished"],
    "values": ["xp", "coins"],
    "tiers": [
        {"days": 2, "multiplier": 1.5},
        {"days": 5, "multiplier": 2.0},
        {"days": 10, "multiplier": 2.5},
    ],
}

LEVEL_REWARDS: list[dict[str, Any]] = [
    {"level": 5, "label": "Bronze", "coins": 100, "contribution": 0, "product": None},
    {"level": 10, "label": "Argent", "coins": 250, "contribution": 5, "product": "badge_binge_watcher"},
    {"level": 20, "label": "Or", "coins": 500, "contribution": 10, "product": "badge_golden_cinephile"},
    {"level": 35, "label": "Platine", "coins": 1000, "contribution": 20, "product": None},
    {"level": 50, "label": "Légende", "coins": 2000, "contribution": 40, "product": None},
]

# --- seasonal campaigns ------------------------------------------------------------------------------------
HORROR = ["horreur", "horror", "thriller", "épouvante", "épouvante-horreur", "horror fiction"]
WATCHED = ["media.playback_finished"]


def campaigns(today: date) -> dict[str, dict[str, Any]]:
    """Yearly campaigns starting this year (or next, once this year's edition is over)."""

    def year_of(month: int, day: int, end_month: int, end_day: int) -> int:
        end = date(today.year + (1 if end_month < month else 0), end_month, end_day)
        return today.year if today <= end else today.year + 1

    halloween = year_of(10, 20, 11, 2)
    christmas = year_of(12, 15, 1, 2)
    cinema = year_of(6, 25, 7, 2)
    return {
        "halloween": {
            "names": {"fr": "Halloween", "en": "Halloween"},
            "description": "Frissons garantis : films, séries, livres et livres audio d'horreur ou thrillers "
            "rapportent double XP et double Coins, et la boutique d'Halloween est à -20 %.",
            "timezone": "Europe/Paris",
            "schedule": {
                "start_at": f"{halloween}-10-20T00:00:00",
                "end_at": f"{halloween}-11-02T23:59:00",
                "recurrence": {"kind": "yearly"},
            },
            "modifiers": [
                {
                    "id": "horror_xp",
                    "value": "xp",
                    "factor": 2,
                    "when": {
                        "activity": WATCHED,
                        "media_kind": ["movie", "series", "episode", "book", "audiobook"],
                        "genre": HORROR,
                    },
                },
                {
                    "id": "horror_coins",
                    "value": "coins",
                    "factor": 2,
                    "when": {
                        "activity": WATCHED,
                        "media_kind": ["movie", "series", "episode", "book", "audiobook"],
                        "genre": HORROR,
                    },
                },
            ],
            "discounts": [
                {
                    "id": "spooky_shop",
                    "percent": 20,
                    "products": [
                        "theme_halloween",
                        "theme_horror",
                        "ultimate_halloween",
                        "ultimate_horror",
                        "banner_halloween",
                        "name_halloween",
                        "name_horror",
                        "frame_pumpkin",
                        "badge_pumpkin_king",
                        "badge_ghost",
                        "effect_pumpkin",
                        "ambient_bats",
                        "ambient_fog",
                        "bg_bats",
                    ],
                    "categories": [],
                }
            ],
            "ending_soon_hours": 48,
        },
        "christmas": {
            "names": {"fr": "Noël", "en": "Christmas"},
            "description": "Les fêtes au chaud : toutes les lectures rapportent 1,5 fois plus d'XP "
            "et la boutique de Noël est à -15 %.",
            "timezone": "Europe/Paris",
            "schedule": {
                "start_at": f"{christmas}-12-15T00:00:00",
                "end_at": f"{christmas + 1}-01-02T23:59:00",
                "recurrence": {"kind": "yearly"},
            },
            "modifiers": [{"id": "festive_xp", "value": "xp", "factor": 1.5, "when": {"activity": WATCHED}}],
            "discounts": [
                {
                    "id": "festive_shop",
                    "percent": 15,
                    "products": [
                        "theme_christmas",
                        "ultimate_christmas",
                        "name_christmas",
                        "badge_elf",
                        "title_head_elf",
                        "ambient_snow",
                        "bg_snow",
                        "effect_snow",
                        "banner_snowfall",
                    ],
                    "categories": [],
                }
            ],
            "ending_soon_hours": 48,
        },
        "cinema_festival": {
            "names": {"fr": "Fête du cinéma", "en": "Cinema festival"},
            "description": "Une semaine pour les films : chaque film terminé rapporte double XP, et les "
            "fonds et ambiances sont à -10 %.",
            "timezone": "Europe/Paris",
            "schedule": {
                "start_at": f"{cinema}-06-25T00:00:00",
                "end_at": f"{cinema}-07-02T23:59:00",
                "recurrence": {"kind": "yearly"},
            },
            "modifiers": [
                {
                    "id": "film_xp",
                    "value": "xp",
                    "factor": 2,
                    "when": {"activity": WATCHED, "media_kind": ["movie"]},
                }
            ],
            "discounts": [
                {
                    "id": "cinema_shop",
                    "percent": 10,
                    "products": [],
                    "categories": ["backgrounds", "ambients"],
                }
            ],
        },
    }


# --- a year of quests ---------------------------------------------------------------------------------------
def _at(day: date) -> str:
    return datetime(day.year, day.month, day.day, tzinfo=PARIS).astimezone(UTC).isoformat()


def _season(today: date, start: tuple[int, int], end: tuple[int, int]) -> tuple[date, date]:
    """The season's next (or current) edition: from ``start`` to ``end`` (exclusive), across New Year."""
    for year in (today.year - 1, today.year, today.year + 1):
        begin = date(year, *start)
        finish = date(year + (1 if end < start else 0), *end)
        if today < finish:
            return begin, finish
    raise AssertionError("unreachable")


def _played(count: int, kinds: list[str] | None = None) -> list[dict[str, Any]]:
    step: dict[str, Any] = {"kind": "event_count", "event_type": "media.playback_finished", "count": count}
    if kinds:
        step["filter"] = [{"field": "kind", "op": "in", "value": kinds}]
    return [step]


def _count(event: str, count: int) -> list[dict[str, Any]]:
    return [{"kind": "event_count", "event_type": event, "count": count}]


def quests(today: date) -> dict[str, dict[str, Any]]:
    """Daily, weekly and monthly objectives for the twelve months ahead, plus one per season."""
    year = (_at(today.replace(month=1, day=1)), _at(date(today.year + 2, 1, 1)))
    span = {"starts_at": year[0], "ends_at": year[1]}

    def seasonal(start: tuple[int, int], end: tuple[int, int]) -> tuple[dict[str, str], int]:
        begin, finish = _season(today, start, end)
        return {"starts_at": _at(begin), "ends_at": _at(finish)}, finish.year

    winter, w_year = seasonal((12, 21), (3, 20))
    spring, s_year = seasonal((3, 20), (6, 21))
    summer, u_year = seasonal((6, 21), (9, 22))
    autumn, a_year = seasonal((9, 22), (12, 21))
    advent, d_year = seasonal((12, 1), (12, 25))
    return {
        "daily_episode": {
            "kind": "daily",
            "period": "day",
            "window": span,
            "icon": "play",
            "label": "Une lecture par jour",
            "description": "Terminez un film, un épisode ou un livre audio.",
            "steps": _played(1),
            "rewards": [{"value": "coins", "amount": 10}],
        },
        "daily_double_feature": {
            "kind": "daily",
            "period": "day",
            "window": span,
            "icon": "clapperboard",
            "label": "Séance double",
            "description": "Deux lectures dans la journée.",
            "steps": _played(2),
            "rewards": [{"value": "xp", "amount": 25}],
        },
        "weekly_marathon": {
            "kind": "daily",
            "period": "week",
            "window": span,
            "icon": "flame",
            "label": "Marathon de la semaine",
            "description": "Cinq lectures cette semaine.",
            "steps": _played(5),
            "rewards": [{"value": "xp", "amount": 60}, {"value": "coins", "amount": 15}],
        },
        "weekly_wish": {
            "kind": "daily",
            "period": "week",
            "window": span,
            "icon": "inbox",
            "label": "Une envie par semaine",
            "description": "Demandez un film ou une série.",
            "steps": _count("media.request_created", 1),
            "rewards": [{"value": "xp", "amount": 20}],
        },
        "weekly_regular_visits": {
            "kind": "daily",
            "period": "week",
            "window": span,
            "icon": "calendar",
            "label": "Habitué de la semaine",
            "description": "Passez sur le portail quatre fois.",
            "steps": _count("user.signed_in", 4),
            "rewards": [{"value": "coins", "amount": 20}],
        },
        "monthly_cinephile": {
            "kind": "daily",
            "period": "month",
            "window": span,
            "icon": "film",
            "label": "Cinéphile du mois",
            "description": "Vingt lectures ce mois-ci.",
            "steps": _played(20),
            "rewards": [{"value": "xp", "amount": 200}, {"value": "coins", "amount": 50}],
        },
        "monthly_voice": {
            "kind": "daily",
            "period": "month",
            "window": span,
            "icon": "message",
            "label": "La voix des membres",
            "description": "Donnez votre avis une fois dans le mois.",
            "steps": _count("feedback.submitted", 1),
            "rewards": [{"value": "xp", "amount": 30}, {"value": "contribution", "amount": 2}],
        },
        "monthly_treat": {
            "kind": "daily",
            "period": "month",
            "window": span,
            "icon": "shop",
            "label": "Une petite folie",
            "description": "Un achat dans la boutique ce mois-ci.",
            "steps": _count("marketplace.purchase", 1),
            "rewards": [{"value": "xp", "amount": 40}],
        },
        f"winter_cosy_{w_year}": {
            "kind": "daily",
            "period": "week",
            "window": winter,
            "icon": "snowflake",
            "label": "Hiver au chaud",
            "description": "Sept lectures par semaine tout l'hiver.",
            "steps": _played(7),
            "rewards": [{"value": "xp", "amount": 90}, {"value": "coins", "amount": 25}],
        },
        f"spring_discoveries_{s_year}": {
            "kind": "daily",
            "period": "month",
            "window": spring,
            "icon": "flower",
            "label": "Printemps des découvertes",
            "description": "Trois demandes de médias par mois.",
            "steps": _count("media.request_created", 3),
            "rewards": [{"value": "xp", "amount": 80}, {"value": "coins", "amount": 20}],
        },
        f"summer_cinema_{u_year}": {
            "kind": "daily",
            "period": "week",
            "window": summer,
            "icon": "sun",
            "label": "Été cinéma",
            "description": "Quatre films par semaine cet été.",
            "steps": _played(4, ["movie"]),
            "rewards": [{"value": "xp", "amount": 70}, {"value": "coins", "amount": 20}],
        },
        f"autumn_reading_{a_year}": {
            "kind": "daily",
            "period": "month",
            "window": autumn,
            "icon": "book",
            "label": "Automne des lectures",
            "description": "Trois livres ou livres audio par mois.",
            "steps": _played(3, ["book", "audiobook"]),
            "rewards": [{"value": "xp", "amount": 120}, {"value": "coins", "amount": 30}],
        },
        f"advent_{d_year}": {
            "kind": "daily",
            "period": "day",
            "window": advent,
            "icon": "gift",
            "label": "Calendrier de l'Avent",
            "description": "Passez chaque jour jusqu'à Noël.",
            "steps": _count("user.signed_in", 1),
            "rewards": [{"value": "coins", "amount": 15}],
        },
        f"year_challenge_{today.year}": {
            "kind": "challenge",
            "period": "none",
            "window": {"starts_at": _at(today), "ends_at": _at(today + timedelta(days=365))},
            "icon": "trophy",
            "label": "Le défi de l'année",
            "description": "Deux cents lectures en un an.",
            "steps": _played(200),
            "rewards": [{"value": "xp", "amount": 1500}, {"value": "coins", "amount": 400}],
        },
    }


# --- a feedback request -------------------------------------------------------------------------------------
FEEDBACK_REQUEST: dict[str, Any] = {
    "key": "portal_survey",
    "kind": "survey",
    "label": "Votre avis sur le nouveau portail",
    "description": "Trois questions, une minute : dites-nous ce que vous pensez de la nouvelle interface.",
    "icon": "star",
    "fields": [
        {"key": "rating", "label": "Votre note globale", "type": "rating", "required": True},
        {
            "key": "favourite",
            "label": "Ce que vous utilisez le plus",
            "type": "multi_select",
            "options": ["media", "shop", "community", "support"],
        },
        {
            "key": "easy",
            "label": "Trouvez-vous facilement ce que vous cherchez ?",
            "type": "select",
            "options": ["yes", "no"],
        },
        {"key": "comment", "label": "Une remarque, une idée ?", "type": "long_text"},
    ],
}
