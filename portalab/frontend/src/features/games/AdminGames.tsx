import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { AdminPage } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { Skeleton } from "../../design-system/components/Placeholders";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type ChallengeItem, GAME_ICONS, useChallenge } from "./api";
import { RewardRules } from "./RewardRules";
import "./games.css";

interface RoundSettings {
  enabled: boolean;
  rounds: number;
  seconds: number;
  choices: number;
}

interface GamesConfig {
  enabled: boolean;
  library: { kinds: string[]; min_votes: number; available_only: boolean };
  rounds: Record<string, RoundSettings>;
  cinemot: { enabled: boolean; tries: number; min_letters: number; max_letters: number };
  memory: { enabled: boolean; pairs: number; own_cards: boolean };
  challenge: {
    enabled: boolean;
    kinds: Record<string, { enabled: boolean; target: number; item: string | null }>;
  };
  party: { enabled: boolean; max_players: number; reveal_seconds: number; countdown_seconds: number };
}

interface Figures {
  solo: { week: number; month: number; players: number } | null;
  party: { parties: number; players: number } | null;
}

interface AdminView {
  key: string;
  config: GamesConfig;
  games: string[];
  round_games: string[];
  solo_only: string[];
  party_only: string[];
  figures: Record<string, Figures>;
}

interface WheelSegment {
  key: string;
  kind: "coins" | "xp" | "product" | "nothing";
  amount: number;
  product?: string | null;
  labels?: Record<string, string>; // none: the wheel shows its amount
  weight: number;
  fallback?: number;
}

const ADMIN = ["admin", "games"] as const;

async function saveSetting(key: string, value: unknown, reason: string) {
  await api.PUT("/api/v1/admin/config", {
    body: { changes: [{ key, value, scope: "global", scope_ref: "", unset: false }], reason } as never,
  });
}

function Num({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
  min: number;
  max: number;
}) {
  return (
    <TextField
      label={label}
      type="number"
      min={min}
      max={max}
      value={String(value)}
      onChange={(e) => onChange(Math.max(min, Math.min(max, Number(e.target.value) || min)))}
    />
  );
}

const KINDS = ["game", "movie", "book", "audiobook"] as const;

/** One of the week's challenges: on or off, its target, a title pinned (else drawn), drawn again now. */
function ChallengeKind({
  kind,
  config,
  set,
  current,
}: {
  kind: (typeof KINDS)[number];
  config: GamesConfig;
  set: (c: GamesConfig) => void;
  current: ChallengeItem | undefined;
}) {
  const t = useT();
  const client = useQueryClient();
  const row = config.challenge.kinds[kind] ?? { enabled: true, target: 30, item: null };
  const change = (next: Partial<typeof row>) =>
    set({
      ...config,
      challenge: { ...config.challenge, kinds: { ...config.challenge.kinds, [kind]: { ...row, ...next } } },
    });
  const [q, setQ] = useState("");
  const found = useQuery({
    queryKey: ["media", "challenge-pick", kind, q],
    enabled: q.length >= 2,
    queryFn: async () =>
      (
        (
          await api.GET("/api/v1/media", {
            params: { query: { kind, q, limit: 8 } as never },
          })
        ).data as unknown as { items: { id: string; title: string; year?: number | null }[] }
      ).items,
  });
  const redraw = useMutation({
    mutationFn: async () =>
      api.POST("/api/v1/admin/games/challenge/redraw", { params: { query: { kind } as never } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["games", "challenge"] }),
  });
  return (
    <div className="games-admin__challenge">
      <h3>{t(`gamification:games.challenge.kind.${kind}`)}</h3>
      <CheckboxField
        label={t("gamification:games.admin.on")}
        checked={row.enabled}
        onChange={(e) => change({ enabled: e.target.checked })}
      />
      <Num
        label={t(kind === "game" ? "gamification:games.admin.minutes" : "gamification:games.admin.percent")}
        value={row.target}
        min={1}
        max={kind === "game" ? 600 : 100}
        onChange={(n) => change({ target: n })}
      />
      {current ? <p>{t("gamification:games.admin.challengeNow", { title: current.title.title })}</p> : null}
      <TextField
        label={t("gamification:games.admin.challengeSearch")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {found.data?.length ? (
        <ul className="games-admin__picks">
          {found.data.map((title) => (
            <li key={title.id}>
              <button
                type="button"
                aria-pressed={row.item === title.id}
                onClick={() => change({ item: title.id })}
              >
                {title.title}
                {title.year ? ` (${title.year})` : ""}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="games-muted">
        {row.item
          ? t("gamification:games.admin.challengePinned")
          : t("gamification:games.admin.challengeRandom")}
      </p>
      <div className="games-actions">
        {row.item ? (
          <Button variant="ghost" onClick={() => change({ item: null })}>
            {t("gamification:games.admin.challengeUnpin")}
          </Button>
        ) : null}
        <Button variant="secondary" disabled={redraw.isPending} onClick={() => redraw.mutate()}>
          <Icon name="dices" size={16} />
          {t("gamification:games.admin.challengeRedraw")}
        </Button>
      </div>
    </div>
  );
}

function ChallengePicker({ config, set }: { config: GamesConfig; set: (c: GamesConfig) => void }) {
  const challenge = useChallenge(config.challenge.enabled);
  const current = Object.fromEntries((challenge.data?.items ?? []).map((item) => [item.kind, item]));
  return (
    <div className="games-admin__kinds-grid">
      {KINDS.map((kind) => (
        <ChallengeKind key={kind} kind={kind} config={config} set={set} current={current[kind]} />
      ))}
    </div>
  );
}

function WheelEditor() {
  const t = useT();
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["admin", "config"],
    queryFn: async () =>
      (
        (await api.GET("/api/v1/admin/config")).data as unknown as {
          settings: { key: string; value: unknown }[];
        }
      ).settings,
  });
  const current = settings.data?.find((s) => s.key === "economy.wheel")?.value as
    | { enabled?: boolean; segments?: WheelSegment[] }
    | undefined;
  const [wheel, setWheel] = useState<{ enabled: boolean; segments: WheelSegment[] } | null>(null);
  useEffect(() => {
    if (current && !wheel) setWheel({ enabled: current.enabled ?? true, segments: current.segments ?? [] });
  }, [current, wheel]);
  const save = useMutation({
    mutationFn: async () => saveSetting("economy.wheel", wheel, "games: the wheel"),
    onSettled: () => client.invalidateQueries({ queryKey: ["admin", "config"] }),
  });
  if (!wheel) return null;
  const edit = (at: number, change: Partial<WheelSegment>) =>
    setWheel({ ...wheel, segments: wheel.segments.map((s, i) => (i === at ? { ...s, ...change } : s)) });
  return (
    <section className="games-panel">
      <h2>
        <Icon name="ferris-wheel" size={18} />
        {t("gamification:games.wheel")}
      </h2>
      <CheckboxField
        label={t("gamification:games.admin.wheelOn")}
        checked={wheel.enabled}
        onChange={(e) => setWheel({ ...wheel, enabled: e.target.checked })}
      />
      <div className="games-admin__table">
        <div className="games-admin__head" aria-hidden="true">
          <span>{t("gamification:games.admin.segLabel")}</span>
          <span>{t("gamification:games.admin.segKind")}</span>
          <span>{t("gamification:games.admin.segAmount")}</span>
          <span>{t("gamification:games.admin.segWeight")}</span>
          <span />
        </div>
        {wheel.segments.map((segment, at) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the wheel's segments in order
          <div key={at}>
            <input
              aria-label={t("gamification:games.admin.segLabel")}
              value={segment.labels?.fr ?? segment.labels?.en ?? ""}
              placeholder={segment.kind === "nothing" ? "—" : `+${segment.amount}`}
              onChange={(e) => edit(at, { labels: { ...(segment.labels ?? {}), fr: e.target.value } })}
            />
            <select
              aria-label={t("gamification:games.admin.segKind")}
              value={segment.kind}
              onChange={(e) => edit(at, { kind: e.target.value as WheelSegment["kind"] })}
            >
              {(["coins", "xp", "product", "nothing"] as const).map((kind) => (
                <option key={kind} value={kind}>
                  {t(`gamification:games.admin.kind.${kind}`)}
                </option>
              ))}
            </select>
            <input
              aria-label={t("gamification:games.admin.segAmount")}
              type="number"
              min={0}
              value={segment.amount}
              disabled={segment.kind === "nothing" || segment.kind === "product"}
              onChange={(e) => edit(at, { amount: Number(e.target.value) || 0 })}
            />
            <input
              aria-label={t("gamification:games.admin.segWeight")}
              type="number"
              min={1}
              value={segment.weight}
              onChange={(e) => edit(at, { weight: Math.max(1, Number(e.target.value) || 1) })}
            />
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("gamification:games.admin.segRemove")}
              onClick={() => setWheel({ ...wheel, segments: wheel.segments.filter((_, i) => i !== at) })}
            >
              <Icon name="trash" size={16} />
            </Button>
          </div>
        ))}
      </div>
      <div className="games-actions">
        <Button
          variant="ghost"
          disabled={wheel.segments.length >= 16}
          onClick={() =>
            setWheel({
              ...wheel,
              segments: [
                ...wheel.segments,
                {
                  key: `segment-${wheel.segments.length + 1}`,
                  kind: "coins",
                  amount: 10,
                  weight: 1,
                },
              ],
            })
          }
        >
          <Icon name="plus" size={16} />
          {t("gamification:games.admin.segAdd")}
        </Button>
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          {t("gamification:games.admin.save")}
        </Button>
      </div>
      {save.error ? <p className="games-error">{save.error.message}</p> : null}
      {save.isSuccess ? <p className="games-muted">{t("gamification:games.admin.saved")}</p> : null}
    </section>
  );
}

/**
 * Issue 265: the games, for the administrators — the page on or off, the titles the games draw from, each
 * game's rounds, time and choices, the day's title, the memory, the week's challenge (a game pinned or drawn
 * again), the parties; what was played; the rewards (reward rules) and the daily wheel.
 */
export default function AdminGames() {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const admin = useQuery({
    queryKey: ADMIN,
    queryFn: async () => (await api.GET("/api/v1/admin/games")).data as unknown as AdminView,
  });
  const [config, setConfig] = useState<GamesConfig | null>(null);
  useEffect(() => {
    if (admin.data && !config) setConfig(admin.data.config);
  }, [admin.data, config]);
  const save = useMutation({
    mutationFn: async () => saveSetting("games.config", config, "games: settings"),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ADMIN });
      void client.invalidateQueries({ queryKey: ["games"] });
    },
  });
  const view = admin.data;
  return (
    <AdminPage
      icon="gamepad"
      title={t("gamification:games.admin.title")}
      description={t("gamification:games.admin.pitch")}
      primary={
        <Button disabled={!config || save.isPending} onClick={() => save.mutate()}>
          {t("gamification:games.admin.save")}
        </Button>
      }
    >
      {!view || !config ? (
        <Skeleton shape="card" label={t("gamification:games.loading")} />
      ) : (
        <div className="games-admin">
          {save.error ? <p className="games-error">{save.error.message}</p> : null}
          {save.isSuccess ? <p className="games-muted">{t("gamification:games.admin.saved")}</p> : null}
          <section className="games-panel">
            <h2>{t("gamification:games.admin.general")}</h2>
            <CheckboxField
              label={t("gamification:games.admin.enabled")}
              checked={config.enabled}
              onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
            />
            <fieldset className="games-admin__kinds">
              <legend>{t("gamification:games.admin.kinds")}</legend>
              {["movie", "series"].map((kind) => (
                <CheckboxField
                  key={kind}
                  label={t(`media:kind.${kind}`)}
                  checked={config.library.kinds.includes(kind)}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      library: {
                        ...config.library,
                        kinds: e.target.checked
                          ? [...config.library.kinds, kind]
                          : config.library.kinds.filter((k) => k !== kind),
                      },
                    })
                  }
                />
              ))}
            </fieldset>
            <div className="games-panel__row">
              <Num
                label={t("gamification:games.admin.minVotes")}
                value={config.library.min_votes}
                min={0}
                max={100000}
                onChange={(n) => setConfig({ ...config, library: { ...config.library, min_votes: n } })}
              />
            </div>
            <CheckboxField
              label={t("gamification:games.admin.availableOnly")}
              checked={config.library.available_only}
              onChange={(e) =>
                setConfig({ ...config, library: { ...config.library, available_only: e.target.checked } })
              }
            />
          </section>

          <section className="games-panel">
            <h2>{t("gamification:games.admin.roundGames")}</h2>
            <div className="games-admin__table games-admin__games">
              <div className="games-admin__head" aria-hidden="true">
                <span>{t("gamification:games.admin.game")}</span>
                <span>{t("gamification:games.admin.on")}</span>
                <span>{t("gamification:games.admin.rounds")}</span>
                <span>{t("gamification:games.admin.seconds")}</span>
                <span>{t("gamification:games.admin.choices")}</span>
                <span>{t("gamification:games.admin.played")}</span>
              </div>
              {view.round_games.map((game) => {
                const row = config.rounds[game] as RoundSettings;
                const set = (change: Partial<RoundSettings>) =>
                  setConfig({ ...config, rounds: { ...config.rounds, [game]: { ...row, ...change } } });
                const figures = view.figures[game];
                return (
                  <div key={game}>
                    <span className="games-admin__name">
                      <Icon name={GAME_ICONS[game] ?? "gamepad"} size={16} />
                      {t(`gamification:games.game.${game}.name`)}
                      {view.solo_only.includes(game) ? (
                        <small>{t("gamification:games.admin.soloOnly")}</small>
                      ) : null}
                      {view.party_only.includes(game) ? (
                        <small>{t("gamification:games.admin.partyOnly")}</small>
                      ) : null}
                    </span>
                    <input
                      type="checkbox"
                      aria-label={t("gamification:games.admin.on")}
                      checked={row.enabled}
                      onChange={(e) => set({ enabled: e.target.checked })}
                    />
                    <input
                      type="number"
                      aria-label={t("gamification:games.admin.rounds")}
                      min={1}
                      max={50}
                      value={row.rounds}
                      onChange={(e) =>
                        set({ rounds: Math.max(1, Math.min(50, Number(e.target.value) || 1)) })
                      }
                    />
                    <input
                      type="number"
                      aria-label={t("gamification:games.admin.seconds")}
                      min={5}
                      max={180}
                      value={row.seconds}
                      onChange={(e) =>
                        set({ seconds: Math.max(5, Math.min(180, Number(e.target.value) || 5)) })
                      }
                    />
                    <input
                      type="number"
                      aria-label={t("gamification:games.admin.choices")}
                      min={2}
                      max={8}
                      value={row.choices}
                      onChange={(e) =>
                        set({ choices: Math.max(2, Math.min(8, Number(e.target.value) || 2)) })
                      }
                    />
                    <span className="games-muted">
                      {format.number(figures?.solo?.month ?? 0)} /{" "}
                      {format.number(figures?.party?.parties ?? 0)}
                    </span>
                  </div>
                );
              })}
            </div>
            <p className="games-muted">{t("gamification:games.admin.playedHint")}</p>
          </section>

          <section className="games-panel">
            <h2>{t("gamification:games.game.cinemot.name")}</h2>
            <CheckboxField
              label={t("gamification:games.admin.on")}
              checked={config.cinemot.enabled}
              onChange={(e) =>
                setConfig({ ...config, cinemot: { ...config.cinemot, enabled: e.target.checked } })
              }
            />
            <div className="games-panel__row">
              <Num
                label={t("gamification:games.admin.tries")}
                value={config.cinemot.tries}
                min={3}
                max={10}
                onChange={(n) => setConfig({ ...config, cinemot: { ...config.cinemot, tries: n } })}
              />
              <Num
                label={t("gamification:games.admin.minLetters")}
                value={config.cinemot.min_letters}
                min={3}
                max={20}
                onChange={(n) => setConfig({ ...config, cinemot: { ...config.cinemot, min_letters: n } })}
              />
              <Num
                label={t("gamification:games.admin.maxLetters")}
                value={config.cinemot.max_letters}
                min={4}
                max={30}
                onChange={(n) => setConfig({ ...config, cinemot: { ...config.cinemot, max_letters: n } })}
              />
            </div>
          </section>

          <section className="games-panel">
            <h2>{t("gamification:games.game.memory.name")}</h2>
            <CheckboxField
              label={t("gamification:games.admin.on")}
              checked={config.memory.enabled}
              onChange={(e) =>
                setConfig({ ...config, memory: { ...config.memory, enabled: e.target.checked } })
              }
            />
            <Num
              label={t("gamification:games.admin.pairs")}
              value={config.memory.pairs}
              min={4}
              max={15}
              onChange={(n) => setConfig({ ...config, memory: { ...config.memory, pairs: n } })}
            />
            <CheckboxField
              label={t("gamification:games.admin.ownCards")}
              checked={config.memory.own_cards}
              onChange={(e) =>
                setConfig({ ...config, memory: { ...config.memory, own_cards: e.target.checked } })
              }
            />
          </section>

          <section className="games-panel">
            <h2>{t("gamification:games.game.challenge.name")}</h2>
            <CheckboxField
              label={t("gamification:games.admin.on")}
              checked={config.challenge.enabled}
              onChange={(e) =>
                setConfig({ ...config, challenge: { ...config.challenge, enabled: e.target.checked } })
              }
            />
            <ChallengePicker config={config} set={setConfig} />
          </section>

          <section className="games-panel">
            <h2>{t("gamification:games.party.title")}</h2>
            <CheckboxField
              label={t("gamification:games.admin.on")}
              checked={config.party.enabled}
              onChange={(e) =>
                setConfig({ ...config, party: { ...config.party, enabled: e.target.checked } })
              }
            />
            <div className="games-panel__row">
              <Num
                label={t("gamification:games.admin.maxPlayers")}
                value={config.party.max_players}
                min={2}
                max={50}
                onChange={(n) => setConfig({ ...config, party: { ...config.party, max_players: n } })}
              />
              <Num
                label={t("gamification:games.admin.revealSeconds")}
                value={config.party.reveal_seconds}
                min={2}
                max={30}
                onChange={(n) => setConfig({ ...config, party: { ...config.party, reveal_seconds: n } })}
              />
              <Num
                label={t("gamification:games.admin.countdown")}
                value={config.party.countdown_seconds}
                min={0}
                max={10}
                onChange={(n) => setConfig({ ...config, party: { ...config.party, countdown_seconds: n } })}
              />
            </div>
          </section>

          <RewardRules />
          <WheelEditor />
        </div>
      )}
    </AdminPage>
  );
}
