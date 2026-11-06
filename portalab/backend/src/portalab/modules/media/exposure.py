"""029: what an extension may read or do with the media (the exposure catalog). Streams and reading
tickets never."""

from portalab.capabilities.exposure import action, committing, read

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
    read(f"{A}/media/book", "A book's sheet (#367)", "La fiche d'un livre"),
    read(f"{A}/media/game", "A game's sheet (#368)", "La fiche d'un jeu"),
    read(f"{A}/media/discover/titles", "Books and games to ask for (#375)", "Livres et jeux à demander"),
    read(f"{A}/media/person/portrait", "A person's portrait", "Le portrait d'une personne"),
    read(f"{A}/media/upcoming", "What is coming soon", "Ce qui arrive bientôt"),
    read(f"{A}/media/discover/search", "Search titles to request", "Chercher des titres à demander"),
    read(f"{A}/media/discover/shelves/{{name}}", "Titles to discover", "Des titres à découvrir"),
    read(f"{A}/media/discover/{{kind}}/{{tmdb_id}}", "A title to request", "Un titre à demander"),
    read(f"{A}/media/discovery/{{shelf}}", "Recommendations", "Des recommandations"),
    read(f"{A}/me/media/continue", "What you are watching", "Ce que vous regardez"),
    # issue 190: my recommendations, the cards to judge, my lists — and saying what I think of a title
    read(f"{A}/me/media/recommendations", "Recommendations for you", "Vos recommandations"),
    read(f"{A}/me/media/taste/deck", "Titles to judge", "Des titres à juger"),
    read(f"{A}/me/media/taste/discover", "Something different for you", "Pour changer, pour vous"),
    read(
        f"{A}/me/media/taste/lists/{{verdict}}",
        "Your lists (liked, later…)",
        "Vos listes (aimés, plus tard…)",
    ),
    read(f"{A}/me/media/taste/titles/{{object_id}}", "What you said of a title", "Votre avis sur un titre"),
    action(
        "PUT", f"{A}/me/media/taste/titles/{{object_id}}", "Like a title, or not", "Aimer un titre, ou non"
    ),
    action(
        "DELETE", f"{A}/me/media/taste/titles/{{object_id}}", "Take back your verdict", "Retirer votre avis"
    ),
    # #299: « Mon fil » — what I follow, and what it brings
    read(f"{A}/me/media/follows", "What you follow", "Ce que vous suivez"),
    action("PUT", f"{A}/me/media/follows", "Follow someone or something", "Suivre une personne, un titre…"),
    action("DELETE", f"{A}/me/media/follows", "Stop following", "Ne plus suivre"),
    read(f"{A}/me/media/feed", "Your feed", "Votre fil"),
    action("POST", f"{A}/me/media/feed/seen", "Mark your feed as read", "Marquer votre fil comme lu"),
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
