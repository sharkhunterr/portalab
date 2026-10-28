/**
 * Issue 265: the games' rewards as Portalab proposes them — reward rules like any other (the administrators
 * change or retire them on the gains' page): a game played, a game won alone, a party won, the day's title
 * found, the week's challenge completed. Bounded per day so that playing all evening stays a pleasure, not
 * a mine.
 */
export const DEFAULT_GAME_RULES: { key: string; definition: Record<string, unknown> }[] = [
  {
    key: "games_played",
    definition: {
      event_type: "games.played",
      label: "Une partie jouée",
      predicate: [],
      grants: [{ value: "xp", amount: 10, per_unit: { field: "score", factor: 0.02, max: 30 } }],
      limits: {
        caps: [{ period: "day", max_amount: 200, value: "xp" }],
        diminishing: { kind: "geometric", period: "day", factor: 0.85 },
      },
    },
  },
  {
    key: "games_won",
    definition: {
      event_type: "games.played",
      label: "Une partie gagnée seul",
      predicate: [
        { field: "won", op: "eq", value: true },
        { field: "mode", op: "eq", value: "solo" },
      ],
      grants: [{ value: "coins", amount: 10 }],
      limits: { caps: [{ period: "day", max_amount: 50, value: "coins" }] },
    },
  },
  {
    key: "games_party_win",
    definition: {
      event_type: "games.played",
      label: "Une partie à plusieurs gagnée",
      predicate: [
        { field: "mode", op: "eq", value: "party" },
        { field: "rank", op: "eq", value: 1 },
        { field: "players", op: "gte", value: 2 },
      ],
      grants: [
        { value: "coins", amount: 25 },
        { value: "xp", amount: 25 },
      ],
      limits: { caps: [{ period: "day", max_amount: 75, value: "coins" }] },
    },
  },
  {
    key: "games_cinemot",
    definition: {
      event_type: "games.played",
      label: "Le ciné-mot du jour trouvé",
      predicate: [
        { field: "game", op: "eq", value: "cinemot" },
        { field: "won", op: "eq", value: true },
      ],
      grants: [{ value: "coins", amount: 20 }],
    },
  },
  {
    key: "games_challenge",
    definition: {
      event_type: "games.challenge_completed",
      label: "Un défi de la semaine (jeu, film, livre, livre audio)",
      predicate: [],
      grants: [
        { value: "xp", amount: 150 },
        { value: "coins", amount: 50 },
      ],
    },
  },
];
