"""029: what a complete interface may read and do of the requests (issue 363) — the exposure catalog. A
request may cost Coins: Portalab confirms it. The administrators' routes are left out (forbidden)."""

from portalab.capabilities.exposure import action, committing, read

A = "/api/v1"
LABELS = (
    read(f"{A}/requests", "My requests and those I may want too", "Mes demandes et celles à soutenir"),
    read(f"{A}/requests/options", "What can be asked for", "Ce qu'on peut demander"),
    committing(
        "POST",
        f"{A}/requests",
        "Ask for a title",
        "Demander un titre",
        confirm_en="Ask the administrators for this title?",
        confirm_fr="Demander ce titre aux administrateurs ?",
    ),
    action("POST", f"{A}/requests/{{request_id}}/support", "Want it too", "Le vouloir aussi"),
    action("DELETE", f"{A}/requests/{{request_id}}/support", "No longer want it", "Ne plus le vouloir"),
)
