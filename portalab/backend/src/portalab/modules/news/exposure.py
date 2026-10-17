"""029: what a complete interface may read of the news (the exposure catalog)."""

from portalab.capabilities.exposure import action, read

A = "/api/v1"
LABELS = (
    read(f"{A}/news", "The news", "Les actualités"),
    read(f"{A}/news/featured", "Featured news", "Les actualités à la une"),
    read(f"{A}/news/categories", "News categories", "Les rubriques"),
    read(f"{A}/news/{{slug}}", "An article", "Un article"),
    action("POST", f"{A}/news/{{slug}}/read", "Mark an article read", "Marquer un article comme lu"),
)
