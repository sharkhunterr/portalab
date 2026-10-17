"""029: what a complete interface may read of the wiki (the exposure catalog)."""

from portalab.capabilities.exposure import read

A = "/api/v1"
LABELS = (
    read(f"{A}/wiki/tree", "The wiki's pages", "Les pages du wiki"),
    read(f"{A}/wiki/pages/{{key}}", "A wiki page", "Une page du wiki"),
)
