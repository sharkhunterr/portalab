"""027 — the discovery missions: a new member's first steps, each rewarded once (``kind: discovery``).

Created when the module starts if their key was never used, so a fresh portal has them; an administrator
may then change or retire them like any quest (a retired one is not created again). Issue 121: each is done
by following its guided tour **or** by doing the thing (``complete_on: any``); a mission still as an earlier
release shipped it (``SUPERSEDED``) is brought up to date at start (#307: so it gains its French texts)."""

from typing import Any

_V1: dict[str, dict[str, Any]] = {
    "discover_profile": {
        "kind": "discovery",
        "label": "Make your profile yours",
        "description": "Add a picture or change your name.",
        "icon": "user",
        "steps": [{"kind": "event_count", "event_type": "user.profile_updated", "count": 1}],
        "rewards": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
    },
    "discover_tour": {
        "kind": "discovery",
        "label": "Take the tour",
        "description": "A minute to see where everything is.",
        "icon": "compass",
        "steps": [
            {
                "kind": "event_count",
                "event_type": "user.onboarding_step_completed",
                "filter": [{"field": "step", "op": "eq", "value": "tour"}],
                "count": 1,
            }
        ],
        "rewards": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
    },
    "discover_dashboard": {
        "kind": "discovery",
        "label": "Arrange your dashboard",
        "description": "Add, move or resize a widget.",
        "icon": "dashboard",
        "steps": [
            {
                "kind": "event_count",
                "event_type": "dashboard.layout_changed",
                "filter": [{"field": "starter", "op": "eq", "value": False}],
                "count": 1,
            }
        ],
        "rewards": [{"value": "xp", "amount": 40}, {"value": "coins", "amount": 20}],
    },
    "discover_request": {
        "kind": "discovery",
        "label": "Ask for a title",
        "description": "Request a film or a series that is not in the library yet.",
        "icon": "inbox",
        "steps": [{"kind": "event_count", "event_type": "media.request_created", "count": 1}],
        "rewards": [{"value": "xp", "amount": 50}, {"value": "coins", "amount": 25}],
    },
    "discover_request_status": {
        "kind": "discovery",
        "label": "Follow a request",
        "description": "See where a request stands on the title's page.",
        "icon": "clock",
        "steps": [
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "request_status"}],
                "count": 1,
            }
        ],
        "rewards": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
    },
    "discover_stats": {
        "kind": "discovery",
        "label": "Read your statistics",
        "description": "What you watched, read and played, in charts.",
        "icon": "chart",
        "steps": [
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "stats"}],
                "count": 1,
            }
        ],
        "rewards": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
    },
    "discover_ticket": {
        "kind": "discovery",
        "label": "Ask the support",
        "description": "Open a ticket: a question, a problem, an idea.",
        "icon": "lifebuoy",
        "steps": [{"kind": "event_count", "event_type": "ticket.created", "count": 1}],
        "rewards": [{"value": "xp", "amount": 30}, {"value": "coins", "amount": 15}],
    },
    "discover_shop": {
        "kind": "discovery",
        "label": "Treat yourself",
        "description": "Get something in the shop with your Coins.",
        "icon": "shop",
        "steps": [{"kind": "event_count", "event_type": "marketplace.purchase", "count": 1}],
        "rewards": [{"value": "xp", "amount": 30}],
    },
}

DISCOVERY: dict[str, dict[str, Any]] = {
    "discover_profile": {
        "kind": "discovery",
        "label": "Make your profile yours",
        "description": "Follow its tour, add a picture or change your name.",
        "icon": "user",
        "steps": [
            {"kind": "event_count", "event_type": "user.profile_updated", "count": 1},
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "profile"}],
                "count": 1,
            },
        ],
        "rewards": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
        "complete_on": "any",
    },
    "discover_tour": {
        "kind": "discovery",
        "label": "Take the tour",
        "description": "A minute to see where everything is.",
        "icon": "compass",
        "steps": [
            {
                "kind": "event_count",
                "event_type": "user.onboarding_step_completed",
                "filter": [{"field": "step", "op": "eq", "value": "tour"}],
                "count": 1,
            },
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "portal"}],
                "count": 1,
            },
        ],
        "rewards": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
        "complete_on": "any",
    },
    "discover_dashboard": {
        "kind": "discovery",
        "label": "Arrange your dashboard",
        "description": "Follow its tour, or add, move or resize a widget.",
        "icon": "dashboard",
        "steps": [
            {
                "kind": "event_count",
                "event_type": "dashboard.layout_changed",
                "filter": [{"field": "starter", "op": "eq", "value": False}],
                "count": 1,
            },
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "dashboard"}],
                "count": 1,
            },
        ],
        "rewards": [{"value": "xp", "amount": 40}, {"value": "coins", "amount": 20}],
        "complete_on": "any",
    },
    "discover_request": {
        "kind": "discovery",
        "label": "Ask for a title",
        "description": "Follow its tour, or request a title that is not in the library yet.",
        "icon": "inbox",
        "steps": [
            {"kind": "event_count", "event_type": "media.request_created", "count": 1},
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "request"}],
                "count": 1,
            },
        ],
        "rewards": [{"value": "xp", "amount": 50}, {"value": "coins", "amount": 25}],
        "complete_on": "any",
    },
    "discover_request_status": {
        "kind": "discovery",
        "label": "Follow a request",
        "description": "See where a request stands on the title's page.",
        "icon": "clock",
        "steps": [
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "request_status"}],
                "count": 1,
            }
        ],
        "rewards": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
    },
    "discover_stats": {
        "kind": "discovery",
        "label": "Read your statistics",
        "description": "What you watched, read and played, in charts.",
        "icon": "chart",
        "steps": [
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "stats"}],
                "count": 1,
            }
        ],
        "rewards": [{"value": "xp", "amount": 25}, {"value": "coins", "amount": 10}],
    },
    "discover_ticket": {
        "kind": "discovery",
        "label": "Ask the support",
        "description": "Follow its tour, or open a ticket: a question, a problem, an idea.",
        "icon": "lifebuoy",
        "steps": [
            {"kind": "event_count", "event_type": "ticket.created", "count": 1},
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "ticket"}],
                "count": 1,
            },
        ],
        "rewards": [{"value": "xp", "amount": 30}, {"value": "coins", "amount": 15}],
        "complete_on": "any",
    },
    "discover_shop": {
        "kind": "discovery",
        "label": "Treat yourself",
        "description": "Follow its tour, or get something in the shop with your Coins.",
        "icon": "shop",
        "steps": [
            {"kind": "event_count", "event_type": "marketplace.purchase", "count": 1},
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "shop"}],
                "count": 1,
            },
        ],
        "rewards": [{"value": "xp", "amount": 30}],
        "complete_on": "any",
    },
    # issue 181: the assistant — follow its tour, or ask it a first question
    "discover_assistant": {
        "kind": "discovery",
        "label": "Meet the assistant",
        "description": "Follow its tour, or ask it a first question.",
        "icon": "sparkles",
        "steps": [
            {"kind": "event_count", "event_type": "ai.answered", "count": 1},
            {
                "kind": "event_count",
                "event_type": "user.tour_completed",
                "filter": [{"field": "tour", "op": "eq", "value": "assistant"}],
                "count": 1,
            },
        ],
        "rewards": [{"value": "xp", "amount": 30}, {"value": "coins", "amount": 15}],
        "complete_on": "any",
    },
}

# #307: their texts in French too — a member reads the missions in their interface's language
FRENCH: dict[str, dict[str, str]] = {
    "discover_profile": {
        "label": "Personnalisez votre profil",
        "description": "Suivez sa visite guidée, ajoutez une photo ou changez votre nom.",
    },
    "discover_tour": {
        "label": "Faites le tour",
        "description": "Une minute pour voir où se trouve chaque chose.",
    },
    "discover_dashboard": {
        "label": "Arrangez votre tableau de bord",
        "description": "Suivez sa visite guidée, ou ajoutez, déplacez ou redimensionnez un widget.",
    },
    "discover_request": {
        "label": "Demandez un titre",
        "description": "Suivez sa visite guidée, ou demandez un titre absent de la bibliothèque.",
    },
    "discover_request_status": {
        "label": "Suivez une demande",
        "description": "Voyez où en est une demande sur la page du titre.",
    },
    "discover_stats": {
        "label": "Consultez vos statistiques",
        "description": "Ce que vous avez regardé, lu et joué, en graphiques.",
    },
    "discover_ticket": {
        "label": "Contactez le support",
        "description": "Suivez sa visite guidée, ou ouvrez un ticket : une question, un problème, une idée.",
    },
    "discover_shop": {
        "label": "Faites-vous plaisir",
        "description": "Suivez sa visite guidée, ou offrez-vous quelque chose dans la boutique.",
    },
    "discover_assistant": {
        "label": "Rencontrez l'assistant",
        "description": "Suivez sa visite guidée, ou posez-lui une première question.",
    },
}
_V2 = DISCOVERY
DISCOVERY = {key: {**raw, "translations": {"fr": FRENCH[key]}} for key, raw in _V2.items()}

# what earlier releases shipped, per key — replaced at start when an administrator never changed it
SUPERSEDED: dict[str, tuple[dict[str, Any], ...]] = {
    key: tuple(old for old in (_V1.get(key), _V2[key]) if old is not None) for key in _V2
}
