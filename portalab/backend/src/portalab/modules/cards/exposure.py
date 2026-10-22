"""029: what a complete interface may read of the media cards (the exposure catalog)."""

from portalab.capabilities.exposure import action, read

A = "/api/v1"
LABELS = (
    read(f"{A}/me/cards", "My card collection", "Ma collection de cartes"),
    read(f"{A}/cards/sets", "The card sets", "Les extensions de cartes"),
    read(f"{A}/cards/sets/{{key}}", "A card set", "Une extension de cartes"),
    read(f"{A}/cards/people", "A person's cards", "Les cartes d'une personne"),
    read(f"{A}/me/cards/packs", "My card packs", "Mes paquets de cartes"),
    action("POST", f"{A}/me/cards/packs/{{pack_id}}/open", "Open a card pack", "Ouvrir un paquet de cartes"),
)
