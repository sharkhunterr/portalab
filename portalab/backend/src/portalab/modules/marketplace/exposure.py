"""029: what a complete interface may read or do in the shop (the exposure catalog). Buying and opening a
booster are committing: they engage the member."""

from portalab.capabilities.exposure import committing, read

A = "/api/v1"
LABELS = (
    read(f"{A}/marketplace/categories", "The shop's categories", "Les rayons de la boutique"),
    read(f"{A}/marketplace/products", "The shop's products", "Les produits de la boutique"),
    read(f"{A}/marketplace/products/{{key}}", "A product", "Un produit"),
    read(f"{A}/marketplace/boosters", "Boosters", "Les boosters"),
    read(f"{A}/marketplace/boosters/openings", "Your booster openings", "Vos ouvertures de boosters"),
    read(f"{A}/marketplace/reserve", "Your reserve", "Votre réserve"),
    read(f"{A}/me/marketplace/purchases", "Your purchases", "Vos achats"),
    read(f"{A}/me/marketplace/requests", "Your special requests", "Vos demandes spéciales"),
    read(f"{A}/projects", "Community projects", "Les projets de la communauté"),
    read(f"{A}/projects/{{project_id}}", "A community project", "Un projet de la communauté"),
    committing(
        "POST",
        f"{A}/marketplace/products/{{key}}/acquire",
        "Buy a product",
        "Acheter un produit",
        confirm_en="Buy « {product} » for {price} Coins",
        confirm_fr="Acheter « {product} » pour {price} Coins",
    ),
    committing(
        "POST",
        f"{A}/projects/{{project_id}}/fund",
        "Fund a community project",
        "Financer un projet",
        confirm_en="Give {amount} Coins to « {project} »",
        confirm_fr="Donner {amount} Coins à « {project} »",
    ),
)
