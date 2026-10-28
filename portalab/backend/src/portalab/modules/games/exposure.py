"""029: what a complete interface may read and do of the games (issue 265) — the exposure catalog. The
administrators' routes are left out (forbidden)."""

from portalab.capabilities.exposure import action, read

A = "/api/v1"
LABELS = (
    read(f"{A}/games", "The games page", "La page des jeux"),
    read(f"{A}/games/leaderboard", "A game's board", "Le classement d'un jeu"),
    action("POST", f"{A}/games/{{game}}/sessions", "Start a game", "Commencer une partie"),
    read(f"{A}/games/sessions/{{session_id}}", "A game in progress", "Une partie en cours"),
    action(
        "POST", f"{A}/games/sessions/{{session_id}}/answer", "Answer a question", "Répondre à une question"
    ),
    action(
        "POST", f"{A}/games/sessions/{{session_id}}/next", "Go on to the next question", "Passer à la suite"
    ),
    action("POST", f"{A}/games/sessions/{{session_id}}/flip", "Turn a card over", "Retourner une carte"),
    read(f"{A}/games/sessions/{{session_id}}/image", "A question's image", "L'image d'une question"),
    read(f"{A}/games/sessions/{{session_id}}/audio", "A question's sound", "Le son d'une question"),
    action("POST", f"{A}/games/memory/sessions", "Start a memory", "Commencer un memory"),
    read(f"{A}/games/cinemot", "The day's title to find", "Le titre du jour à trouver"),
    action("POST", f"{A}/games/cinemot/guesses", "Guess the day's title", "Proposer le titre du jour"),
    read(f"{A}/games/challenge", "The week's challenges", "Les défis de la semaine"),
    read(f"{A}/games/parties", "My parties", "Mes parties à plusieurs"),
    action("POST", f"{A}/games/parties", "Open a party", "Ouvrir une partie à plusieurs"),
    read(f"{A}/games/parties/{{code}}", "A party", "Une partie à plusieurs"),
    action("POST", f"{A}/games/parties/{{code}}/join", "Join a party", "Rejoindre une partie"),
    action("POST", f"{A}/games/parties/{{code}}/leave", "Leave a party", "Quitter une partie"),
    action("POST", f"{A}/games/parties/{{code}}/start", "Start a party", "Lancer une partie"),
    action("POST", f"{A}/games/parties/{{code}}/answer", "Answer in a party", "Répondre dans une partie"),
    action("POST", f"{A}/games/parties/{{code}}/next", "Move a party on", "Faire avancer une partie"),
    read(f"{A}/games/parties/{{code}}/image", "A party question's image", "L'image d'une question"),
    read(f"{A}/games/parties/{{code}}/audio", "A party question's sound", "Le son d'une question"),
)
