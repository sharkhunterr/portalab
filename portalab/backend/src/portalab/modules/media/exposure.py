"""029: what an extension may read or do with the media (the exposure catalog). Streams and reading
tickets never."""

from portalab.capabilities.exposure import committing, read

A = "/api/v1"
LABELS = (
    read(f"{A}/media", "Browse the library", "Parcourir la médiathèque"),
    read(f"{A}/media/facets", "The library's filters", "Les filtres de la médiathèque"),
    read(f"{A}/media/{{object_id}}", "A title's details", "Le détail d'un titre"),
    read(f"{A}/media/{{object_id}}/metadata", "A title's information", "Les informations d'un titre"),
    read(f"{A}/media/{{object_id}}/sections/{{name}}", "A title's sections", "Les sections d'un titre"),
    read(f"{A}/media/images/{{image_id}}", "Posters and pictures", "Affiches et images"),
    read(f"{A}/media/metadata-images", "Posters and backdrops", "Affiches et fonds"),
    read(f"{A}/media/person", "A person's filmography", "La filmographie d'une personne"),
    read(f"{A}/media/person/portrait", "A person's portrait", "Le portrait d'une personne"),
    read(f"{A}/media/upcoming", "What is coming soon", "Ce qui arrive bientôt"),
    read(f"{A}/media/discover/search", "Search titles to request", "Chercher des titres à demander"),
    read(f"{A}/media/discover/shelves/{{name}}", "Titles to discover", "Des titres à découvrir"),
    read(f"{A}/media/discover/{{kind}}/{{tmdb_id}}", "A title to request", "Un titre à demander"),
    read(f"{A}/media/discovery/{{shelf}}", "Recommendations", "Des recommandations"),
    read(f"{A}/me/media/continue", "What you are watching", "Ce que vous regardez"),
    read(f"{A}/me/media/history", "Your watch history", "Votre historique"),
    read(f"{A}/me/media/now-playing", "What is playing now", "Ce qui joue en ce moment"),
    read(f"{A}/me/media/requests", "Your requests", "Vos demandes"),
    read(f"{A}/me/media/requests/list", "Your requests, listed", "Vos demandes, en liste"),
    read(f"{A}/me/media/requests/quota", "Your request quota", "Votre quota de demandes"),
    committing(
        "POST",
        f"{A}/media/requests",
        "Request a title",
        "Demander un titre",
        confirm_en="Request « {title} »",
        confirm_fr="Demander « {title} »",
    ),
    committing(
        "POST",
        f"{A}/media/requests/{{request_id}}/cancel",
        "Cancel a request",
        "Annuler une demande",
        confirm_en="Cancel your request",
        confirm_fr="Annuler votre demande",
    ),
)
