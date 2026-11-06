"""029: what a complete interface may read of the requests to the team (issue 363) — the exposure catalog.
Asking for a title is the media's request (``/media/requests``)."""

from portalab.capabilities.exposure import read

A = "/api/v1"
LABELS = (
    read(f"{A}/requests/options", "The kinds of titles asked of the team", "Ce qu'on demande à l'équipe"),
)
