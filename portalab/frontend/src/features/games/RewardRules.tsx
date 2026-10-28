import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink } from "react-router";
import { api } from "../../api/client";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { type Translate, useT } from "../../i18n/hooks/useT";
import { keyOf } from "../gamification/admin/tuning";
import { ROUND_GAMES } from "./api";
import { DEFAULT_GAME_RULES } from "./rewards";
import "./games.css";

/**
 * Issue 265: what the games give — reward rules like any other, kept with them on the gains' page (« XP per
 * action »): a rule made there in a few choices — a game played, a minimum score, a game won, a place in a
 * party, a place on a game's board when the week or the month is over, a challenge of the week; XP and Coins,
 * capped per day — and the rules' conditions said in words. The games' page only leads there.
 */

interface Condition {
  field: string;
  op: "eq" | "ne" | "in" | "gt" | "gte" | "lt" | "lte";
  value: string | number | boolean | Array<string | number>;
}

interface Definition {
  event_type: string;
  label?: string;
  predicate?: Condition[];
  grants?: { value: string; amount?: number | null; per_unit?: { field: string; factor: number } | null }[];
  limits?: { caps?: { period: string; max_amount: number; value: string }[] };
}

interface Rule {
  key: string;
  version: number;
  status: string;
  event_type: string;
  definition: Definition;
}

const KINDS = ["played", "score", "won", "party", "board", "challenge"] as const;
type Kind = (typeof KINDS)[number];
const KIND_ICONS: Record<Kind, string> = {
  played: "gamepad",
  score: "target",
  won: "trophy",
  party: "users",
  board: "medal",
  challenge: "flag",
};
/** the games one can play alone (and so have a board), the day's title and the memory with them */
const SOLO_GAMES = [...ROUND_GAMES.filter((g) => g !== "whowatched"), "cinemot", "memory"];
const PARTY_GAMES = ROUND_GAMES.filter((g) => g !== "memories");
const CHALLENGE_KINDS = ["game", "movie", "book", "audiobook"];

interface Draft {
  kind: Kind;
  game: string; // "" : every game
  score: string;
  rank: string;
  period: "week" | "month";
  challenge: string; // "" : every kind
  xp: string;
  coins: string;
  capXp: string;
  capCoins: string;
  label: string;
}

const EMPTY: Draft = {
  kind: "played",
  game: "",
  score: "500",
  rank: "3",
  period: "week",
  challenge: "",
  xp: "10",
  coins: "0",
  capXp: "200",
  capCoins: "",
  label: "",
};

const gameName = (t: Translate, game: string) =>
  game === "party"
    ? t("gamification:games.party.wins")
    : game === "challenge"
      ? t("gamification:games.admin.rule.challenges")
      : t(`gamification:games.game.${game}.name`);

/** The rule's name when the administrator gives none: what it rewards, in words. */
function labelOf(t: Translate, draft: Draft): string {
  const game = draft.game ? gameName(t, draft.game) : t("gamification:games.admin.rule.anyGame");
  return t(`gamification:games.admin.rule.name.${draft.kind}`, {
    game,
    score: draft.score,
    rank: draft.rank,
    period: t(`gamification:games.admin.rule.period.${draft.period}`),
    kind: draft.challenge
      ? t(`gamification:games.challenge.kind.${draft.challenge}`)
      : t("gamification:games.admin.rule.anyChallenge"),
  });
}

function definitionOf(t: Translate, draft: Draft): Definition {
  const predicate: Condition[] = [];
  let event = "games.played";
  if (draft.kind === "board") {
    event = "games.board_ranked";
    predicate.push({ field: "period", op: "eq", value: draft.period });
    predicate.push({ field: "rank", op: "lte", value: Math.max(1, Number(draft.rank) || 1) });
  } else if (draft.kind === "challenge") {
    event = "games.challenge_completed";
    if (draft.challenge) predicate.push({ field: "kind", op: "eq", value: draft.challenge });
  } else if (draft.kind === "score") {
    predicate.push({ field: "score", op: "gte", value: Math.max(0, Number(draft.score) || 0) });
  } else if (draft.kind === "won") {
    predicate.push({ field: "won", op: "eq", value: true });
    predicate.push({ field: "mode", op: "in", value: ["solo", "daily"] });
  } else if (draft.kind === "party") {
    predicate.push({ field: "mode", op: "eq", value: "party" });
    predicate.push({ field: "rank", op: "lte", value: Math.max(1, Number(draft.rank) || 1) });
    predicate.push({ field: "players", op: "gte", value: 2 });
  }
  if (draft.game && draft.kind !== "challenge")
    predicate.unshift({ field: "game", op: "eq", value: draft.game });
  const grants = [
    { value: "xp", amount: Math.round(Number(draft.xp) || 0) },
    { value: "coins", amount: Math.round(Number(draft.coins) || 0) },
  ].filter((g) => g.amount > 0);
  const caps = [
    { period: "day", max_amount: Math.round(Number(draft.capXp) || 0), value: "xp" },
    { period: "day", max_amount: Math.round(Number(draft.capCoins) || 0), value: "coins" },
  ].filter((c) => c.max_amount > 0 && grants.some((g) => g.value === c.value));
  return {
    event_type: event,
    label: draft.label.trim() || labelOf(t, draft),
    predicate,
    grants,
    limits: { caps },
  };
}

/** A rule's conditions as short chips: the game, the score, the place… */
export function gameRuleChips(t: Translate, eventType: string, predicate: Condition[]): string[] {
  const out: string[] = [];
  const board = eventType === "games.board_ranked";
  for (const c of predicate) {
    const v = Array.isArray(c.value) ? c.value.join(", ") : String(c.value);
    if (c.field === "game" && c.op === "eq") out.push(gameName(t, v));
    else if (c.field === "score") out.push(t("gamification:games.admin.rule.chip.score", { score: v }));
    else if (c.field === "won") out.push(t("gamification:games.admin.rule.chip.won"));
    else if (c.field === "rank")
      out.push(t(`gamification:games.admin.rule.chip.${board ? "boardRank" : "partyRank"}`, { rank: v }));
    else if (c.field === "period") out.push(t(`gamification:games.admin.rule.period.${v}`));
    else if (c.field === "kind") out.push(t(`gamification:games.challenge.kind.${v}`));
    else if (c.field === "mode" || c.field === "players") continue;
    else out.push(`${c.field} ${c.op} ${v}`);
  }
  return out;
}

export function useGameRules() {
  return useQuery({
    queryKey: ["gamification", "rules", "games"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/gamification/rules")).data as unknown as Rule[]).filter((r) =>
        r.event_type.startsWith("games."),
      ),
  });
}

async function saveAndPublish(key: string, definition: Definition) {
  const saved = (
    await api.POST("/api/v1/admin/gamification/rules/{key}", {
      params: { path: { key } },
      body: { definition: definition as unknown as Record<string, unknown> },
    })
  ).data as unknown as Rule;
  await api.POST("/api/v1/admin/gamification/rules/{key}/publish", {
    params: { path: { key } },
    body: { version: saved.version },
  });
}

export function GameRuleBuilder({ taken, onDone }: { taken: Set<string>; onDone: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const set = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });
  const definition = definitionOf(t, draft);
  const create = useMutation({
    mutationFn: async () => {
      let key = `games_${keyOf(definition.label ?? draft.kind)}`.slice(0, 60);
      for (let n = 2; taken.has(key); n += 1) key = `${key.replace(/_\d+$/, "")}_${n}`;
      await saveAndPublish(key, definition);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["gamification", "rules"] });
      onDone();
    },
  });
  const games =
    draft.kind === "party"
      ? PARTY_GAMES
      : draft.kind === "board"
        ? [...SOLO_GAMES, "party", "challenge"]
        : SOLO_GAMES;
  return (
    <form
      className="games-rule-builder"
      onSubmit={(event) => {
        event.preventDefault();
        create.mutate();
      }}
    >
      <fieldset className="games-rule-kinds">
        <legend>{t("gamification:games.admin.rule.what")}</legend>
        {KINDS.map((kind) => (
          <button
            key={kind}
            type="button"
            aria-pressed={draft.kind === kind}
            onClick={() => set({ kind, game: kind === "challenge" ? "" : draft.game })}
          >
            <Icon name={KIND_ICONS[kind]} size={18} />
            <b>{t(`gamification:games.admin.rule.kind.${kind}`)}</b>
            <span>{t(`gamification:games.admin.rule.hint.${kind}`)}</span>
          </button>
        ))}
      </fieldset>
      <div className="games-panel__row">
        {draft.kind === "challenge" ? (
          <SelectField
            label={t("gamification:games.admin.rule.challenge")}
            value={draft.challenge}
            onChange={(e) => set({ challenge: e.target.value })}
          >
            <option value="">{t("gamification:games.admin.rule.anyChallenge")}</option>
            {CHALLENGE_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {t(`gamification:games.challenge.kind.${kind}`)}
              </option>
            ))}
          </SelectField>
        ) : (
          <SelectField
            label={t("gamification:games.admin.rule.game")}
            value={draft.game}
            onChange={(e) => set({ game: e.target.value })}
          >
            <option value="">{t("gamification:games.admin.rule.anyGame")}</option>
            {games.map((game) => (
              <option key={game} value={game}>
                {gameName(t, game)}
              </option>
            ))}
          </SelectField>
        )}
        {draft.kind === "score" ? (
          <TextField
            label={t("gamification:games.admin.rule.minScore")}
            type="number"
            min={0}
            value={draft.score}
            onChange={(e) => set({ score: e.target.value })}
          />
        ) : null}
        {draft.kind === "party" || draft.kind === "board" ? (
          <SelectField
            label={t("gamification:games.admin.rule.rank")}
            value={draft.rank}
            onChange={(e) => set({ rank: e.target.value })}
          >
            {["1", "2", "3", "5", "10"].map((rank) => (
              <option key={rank} value={rank}>
                {t("gamification:games.admin.rule.topN", { rank: Number(rank) })}
              </option>
            ))}
          </SelectField>
        ) : null}
        {draft.kind === "board" ? (
          <SelectField
            label={t("gamification:games.admin.rule.periodLabel")}
            value={draft.period}
            onChange={(e) => set({ period: e.target.value as Draft["period"] })}
          >
            <option value="week">{t("gamification:games.admin.rule.period.week")}</option>
            <option value="month">{t("gamification:games.admin.rule.period.month")}</option>
          </SelectField>
        ) : null}
      </div>
      <div className="games-panel__row">
        <TextField
          label={t("gamification:games.admin.rule.xp")}
          type="number"
          min={0}
          value={draft.xp}
          onChange={(e) => set({ xp: e.target.value })}
        />
        <TextField
          label={t("gamification:games.admin.rule.coins")}
          type="number"
          min={0}
          value={draft.coins}
          onChange={(e) => set({ coins: e.target.value })}
        />
        <TextField
          label={t("gamification:games.admin.rule.capXp")}
          hint={t("gamification:games.admin.rule.capHint")}
          type="number"
          min={0}
          value={draft.capXp}
          onChange={(e) => set({ capXp: e.target.value })}
        />
        <TextField
          label={t("gamification:games.admin.rule.capCoins")}
          type="number"
          min={0}
          value={draft.capCoins}
          onChange={(e) => set({ capCoins: e.target.value })}
        />
      </div>
      <TextField
        label={t("gamification:games.admin.rule.label")}
        placeholder={labelOf(t, draft)}
        maxLength={120}
        value={draft.label}
        onChange={(e) => set({ label: e.target.value })}
      />
      <div className="games-actions">
        <Button type="submit" disabled={create.isPending || !definition.grants?.length}>
          <Icon name="plus" size={16} />
          {t("gamification:games.admin.rule.create")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("gamification:games.admin.rule.cancel")}
        </Button>
      </div>
      {create.error ? <p className="games-error">{create.error.message}</p> : null}
    </form>
  );
}

/** Issue 265: the rules Portalab proposes for the games, added in one go (those missing, published). */
export function useProposedGameRules() {
  const client = useQueryClient();
  const rules = useGameRules();
  const missing =
    Boolean(rules.data) && DEFAULT_GAME_RULES.some((d) => !rules.data?.some((r) => r.key === d.key));
  const create = useMutation({
    mutationFn: async () => {
      const taken = new Set((rules.data ?? []).map((r) => r.key));
      for (const rule of DEFAULT_GAME_RULES)
        if (!taken.has(rule.key)) await saveAndPublish(rule.key, rule.definition as unknown as Definition);
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["gamification", "rules"] }),
  });
  return { missing, create };
}

/** The games' page: what the games give is set with the other gains — a word, how many rules, the way there. */
export function GameRulesLink() {
  const t = useT();
  const rules = useGameRules();
  const active = (rules.data ?? []).filter((r) => r.status === "active").length;
  return (
    <section className="games-panel">
      <h2>
        <Icon name="coins" size={18} />
        {t("gamification:games.admin.rewards")}
      </h2>
      <p className="games-muted">{t("gamification:games.admin.rewardsThere")}</p>
      <p>
        {active
          ? t("gamification:games.admin.rewardsCount", { count: active })
          : t("gamification:games.admin.noRewards")}
      </p>
      <div className="games-actions">
        <Button asChild>
          <RouterLink to="/admin/gamification?tab=gains&mode=detailed#games-rules">
            <Icon name="zap" size={16} />
            {t("gamification:games.admin.editRewards")}
          </RouterLink>
        </Button>
      </div>
    </section>
  );
}
