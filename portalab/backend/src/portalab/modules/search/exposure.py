"""029: what a complete interface may search (the exposure catalog)."""

from portalab.capabilities.exposure import action, read

A = "/api/v1"
LABELS = (
    action("POST", f"{A}/search", "Search the portal", "Chercher dans le portail"),
    read(f"{A}/search/suggest", "Search suggestions", "Les suggestions de recherche"),
)
