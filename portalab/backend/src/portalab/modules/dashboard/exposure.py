"""029: what a complete interface may read of the member's dashboard (the exposure catalog)."""

from portalab.capabilities.exposure import read

A = "/api/v1"
LABELS = (
    read(f"{A}/dashboard", "Your dashboard", "Votre tableau de bord"),
    read(f"{A}/dashboard/catalog", "The widgets one may add", "Les widgets disponibles"),
    read(
        f"{A}/dashboard/since-last-login",
        "What happened since your last visit",
        "Ce qui s'est passé depuis votre dernière visite",
    ),
)
