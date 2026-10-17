"""029: what a complete interface may read or do in the community (the exposure catalog)."""

from portalab.capabilities.exposure import committing, read

A = "/api/v1"
LABELS = (
    read(f"{A}/community/feed", "The community's feed", "Le fil de la communauté"),
    read(f"{A}/community/members", "The members", "Les membres"),
    read(f"{A}/community/members/{{member_id}}", "A member's profile", "Le profil d'un membre"),
    read(
        f"{A}/community/members/{{member_id}}/sections/{{name}}",
        "A profile's sections",
        "Les sections d'un profil",
    ),
    read(f"{A}/community/discovery", "Community picks", "Les choix de la communauté"),
    read(f"{A}/community/discovery/{{shelf}}", "Community picks", "Les choix de la communauté"),
    read(f"{A}/community/events", "Community events", "Les événements"),
    read(f"{A}/community/events/{{event_id}}", "An event", "Un événement"),
    read(f"{A}/community/proposals", "Proposals", "Les propositions"),
    read(f"{A}/community/proposals/{{proposal_id}}", "A proposal", "Une proposition"),
    read(f"{A}/community/achievements", "Community achievements", "Les succès de la communauté"),
    read(f"{A}/community/quests", "Community quests", "Les quêtes de la communauté"),
    committing(
        "POST",
        f"{A}/community/proposals/{{proposal_id}}/vote",
        "Vote for a proposal",
        "Voter pour une proposition",
        confirm_en="Vote for « {title} »",
        confirm_fr="Voter pour « {title} »",
    ),
    committing(
        "POST",
        f"{A}/community/proposals",
        "Publish a proposal",
        "Publier une proposition",
        confirm_en="Publish this proposal",
        confirm_fr="Publier cette proposition",
    ),
)
