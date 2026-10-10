"""027 — the discovery missions: a new member's first steps, each rewarded once (``kind: discovery``).

Created when the module starts if their key was never used, so a fresh portal has them; an administrator
may then change or retire them like any quest (a retired one is not created again)."""

from typing import Any

DISCOVERY: dict[str, dict[str, Any]] = {
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
