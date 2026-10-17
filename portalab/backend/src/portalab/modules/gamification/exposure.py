"""029: what a complete interface may read of the member's progression (the exposure catalog)."""

from portalab.capabilities.exposure import read

A = "/api/v1"
LABELS = (
    read(
        f"{A}/me/progression",
        "Your level, XP and Coins",
        "Votre niveau, votre XP et vos Coins",
        topics=("progression.changed",),
    ),
    read(f"{A}/me/progression/timeline", "Your progression over time", "Votre progression dans le temps"),
    read(f"{A}/me/progression/sources", "Where your XP comes from", "D'où vient votre XP"),
    read(f"{A}/me/achievements", "Your achievements", "Vos succès"),
    read(f"{A}/achievements/catalog", "Every achievement", "Tous les succès"),
    read(f"{A}/me/quests", "Your quests", "Vos quêtes"),
    read(f"{A}/me/streak", "Your streak", "Votre série"),
    read(f"{A}/me/economy/transactions", "Your Coins' history", "L'historique de vos Coins"),
    read(f"{A}/leaderboards", "Leaderboards", "Les classements"),
    read(f"{A}/leaderboards/{{metric}}", "A leaderboard", "Un classement"),
    read(
        f"{A}/me/leaderboard-position", "Your place in the leaderboards", "Votre place dans les classements"
    ),
)
