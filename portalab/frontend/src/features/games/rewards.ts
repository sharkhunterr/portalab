/**
 * Issue 265: the games' rewards as Portalab proposes them — reward rules like any other (the administrators
 * change or retire them on the gains' page): a game played, a game won alone, a party won, the day's title
 * found, a podium on a game's board when the week is over, the week's challenge completed, a line of the month's
 * bingo and its full card (issue 356). Bounded per day so that playing all evening stays a pleasure, not
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
    key: "games_board_week",
    definition: {
      event_type: "games.board_ranked",
      label: "Sur le podium d'un jeu, la semaine finie",
      predicate: [
        { field: "period", op: "eq", value: "week" },
        { field: "rank", op: "lte", value: 3 },
      ],
      grants: [
        { value: "xp", amount: 50 },
        { value: "coins", amount: 20 },
      ],
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
  // issue 356: the month's media bingo — each line, then the full card (with a booster)
  {
    key: "games_bingo_line",
    definition: {
      event_type: "games.bingo_line",
      label: "Une ligne du bingo du mois",
      predicate: [],
      grants: [
        { value: "xp", amount: 30 },
        { value: "coins", amount: 10 },
      ],
    },
  },
  {
    key: "games_bingo_card",
    definition: {
      event_type: "games.bingo_card",
      label: "Le carton plein du bingo du mois",
      predicate: [],
      grants: [
        { value: "xp", amount: 200 },
        { value: "coins", amount: 100 },
      ],
      boosters: 1,
    },
  },
];
