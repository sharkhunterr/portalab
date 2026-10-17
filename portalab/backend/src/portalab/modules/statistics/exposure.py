"""029: what a complete interface may read of the statistics (the exposure catalog)."""

from portalab.capabilities.exposure import read

A = "/api/v1"
LABELS = (
    read(f"{A}/statistics/catalog", "The statistics one may see", "Les statistiques disponibles"),
    read(f"{A}/statistics/{{key}}", "A statistic", "Une statistique"),
)
