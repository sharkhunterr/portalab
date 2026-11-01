import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router";
import { api } from "../../api/client";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { Skeleton } from "../../design-system/components/Placeholders";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useActiveCampaigns } from "../campaigns/api";
import type { WidgetPayload } from "../dashboard/api";
import { ordered, type QuestItem, useQuestText } from "../gamification/quests/QuestList";
import { WheelWidget } from "../gamification/wheel/WheelWidget";
import { imageUrl } from "../media/api";
import { type ChallengeItem, GAME_ICONS, gamesLeft, type HubGame, useChallenge, useGamesHub } from "./api";
import { Board } from "./Boards";
import "./games.css";

function Wheel() {
  const t = useT();
  const wheel = useQuery({
    queryKey: ["widget", "gamification.daily_wheel", "games"],
    retry: false,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/me/wheel");
      return {
        as_of: null,
        config_invalid: false,
        data: data as unknown as Record<string, unknown>,
        partial_reasons: [],
        stale_after_s: null,
        state: "available",
      } satisfies WidgetPayload;
    },
  });
  if (!wheel.data?.data) return null;
  return (
    <article className="games-today__card games-today__wheel">
      <h3>
        <Icon name="ferris-wheel" size={18} />
        {t("gamification:games.wheel")}
      </h3>
      <div className="games-today__wheel-body">
        <WheelWidget payload={wheel.data} config={{}} />
      </div>
    </article>
  );
}

function Cinemot({ status }: { status: { status: string; won: boolean } | null }) {
  const t = useT();
  const state = !status ? "new" : status.status === "playing" ? "playing" : status.won ? "won" : "lost";
  return (
    <article className="games-today__card games-today__cinemot" data-game="cinemot" data-state={state}>
      <h3>
        <Icon name="type" size={18} />
        {t("gamification:games.game.cinemot.name")}
      </h3>
      <div className="games-today__letters" aria-hidden="true">
        {["?", "?", "?", "?", "?"].map((letter, at) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: a decoration
          <span key={at} data-mark={state === "won" ? "right" : at === 1 ? "elsewhere" : undefined}>
            {letter}
          </span>
        ))}
      </div>
      <p>{t(`gamification:games.cinemot.state.${state}`)}</p>
      <Button asChild variant={state === "new" || state === "playing" ? "primary" : "secondary"}>
        <RouterLink to="/games/cinemot">
          <Icon name={state === "won" || state === "lost" ? "eye" : "play"} size={16} />
          {state === "won" || state === "lost"
            ? t("gamification:games.cinemot.see")
            : t("gamification:games.play")}
        </RouterLink>
      </Button>
    </article>
  );
}

/** Issue 313: a reminder of the quests — how many are done, today's still to do, the next one to close —
 * leading to their tab. */
function QuestReminder() {
  const t = useT();
  const format = useFormat();
  const text = useQuestText();
  const quests = useQuery({
    queryKey: ["community", "quests"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/community/quests")).data,
  });
  const items = (quests.data?.state === "unavailable"
    ? []
    : (quests.data?.items ?? [])) as unknown as QuestItem[];
  if (!items.length) return null;
  const { open, done } = ordered(items);
  const today = open.filter((q) => q.period === "day").length;
  const next = open[0];
  return (
    <RouterLink
      to="/games/quests"
      className="games-reminder"
      data-reminder="quests"
      data-complete={open.length === 0 || undefined}
    >
      <span className="games-reminder__icon" aria-hidden="true">
        <Icon name={open.length ? "target" : "trophy"} size={20} />
      </span>
      <span className="games-reminder__body">
        <span className="games-reminder__head">
          <b>{t("gamification:quests.summary")}</b>
          <span>
            {format.number(done.length)} / {format.number(items.length)}
          </span>
        </span>
        <span className="ds-bar" aria-hidden="true">
          <span
            className="ds-bar__fill"
            style={{ inlineSize: `${Math.round((done.length / items.length) * 100)}%` }}
          />
        </span>
        <span className="games-muted">
          {open.length
            ? [
                t("gamification:games.quests.today", { count: today }),
                next ? t("gamification:games.quests.next", { label: text(next).label }) : null,
              ]
                .filter(Boolean)
                .join(" · ")
            : t("gamification:games.quests.allDone")}
        </span>
      </span>
      <span className="games-reminder__more">
        {t("gamification:games.quests.see")}
        <Icon name="chevron-right" size={16} />
      </span>
    </RouterLink>
  );
}

/** Issue 313: the campaigns running now — what they boost (each boost once) and until when — each leading to its page. */
function CampaignReminders() {
  const t = useT();
  const format = useFormat();
  const active = useActiveCampaigns();
  return (active.data ?? []).map((campaign) => (
    <RouterLink
      key={campaign.key}
      to={`/campaigns/${campaign.key}`}
      className="games-reminder"
      data-reminder="campaign"
    >
      <span className="games-reminder__icon" aria-hidden="true">
        <Icon name="star" size={20} />
      </span>
      <span className="games-reminder__body">
        <span className="games-reminder__head">
          <b>{campaign.name}</b>
          {campaign.ends_at ? (
            <span>{t("campaigns:banner.ends", { date: format.date(campaign.ends_at) })}</span>
          ) : null}
        </span>
        <span className="games-muted">
          {campaign.boosts.length
            ? [
                ...new Set(
                  campaign.boosts.map(
                    (boost) => `×${boost.factor} ${t(`gamification:value.${boost.value}`)}`,
                  ),
                ),
              ].join(" · ")
            : t("campaigns:banner.label")}
        </span>
      </span>
      <span className="games-reminder__more">
        {t("gamification:games.campaign.see")}
        <Icon name="chevron-right" size={16} />
      </span>
    </RouterLink>
  ));
}

const CHALLENGE_ICONS: Record<string, string> = {
  game: "joystick",
  movie: "film",
  book: "book",
  audiobook: "headphones",
};

function ChallengeCard({ item }: { item: ChallengeItem }) {
  const t = useT();
  const format = useFormat();
  const share = Math.min(1, item.mine / item.target);
  const icon = CHALLENGE_ICONS[item.kind] ?? "gamepad";
  return (
    <li className="games-challenge" data-kind={item.kind} data-done={item.done || undefined}>
      <div className="games-challenge__cover">
        {item.title.image_id ? (
          <img src={imageUrl(item.title.image_id) ?? ""} alt="" />
        ) : (
          <Icon name={icon} size={32} />
        )}
        {item.done ? (
          <span className="games-challenge__done" aria-hidden="true">
            <Icon name="check" size={18} />
          </span>
        ) : null}
      </div>
      <div className="games-challenge__body">
        <span className="games-challenge__kind">
          <Icon name={icon} size={14} />
          {t(`gamification:games.challenge.kind.${item.kind}`)}
        </span>
        <RouterLink className="games-challenge__title" to={`/media/${item.title.id}`}>
          {item.title.title}
        </RouterLink>
        {item.title.platform ? <span className="games-muted">{item.title.platform}</span> : null}
        <div
          className="games-progress"
          role="progressbar"
          aria-label={t(`gamification:games.challenge.goal.${item.unit}`, { target: item.target })}
          aria-valuemin={0}
          aria-valuemax={item.target}
          aria-valuenow={item.mine}
        >
          <span style={{ inlineSize: `${share * 100}%` }} />
        </div>
        <p className="games-challenge__figures">
          {item.done ? (
            <b>{t("gamification:games.challenge.done")}</b>
          ) : (
            <>
              <b>
                {t(`gamification:games.challenge.short.${item.unit}`, {
                  mine: format.number(item.mine),
                  target: item.target,
                })}
              </b>
              <span className="games-muted">
                {t("gamification:games.challenge.until", { until: format.date(item.ends_at) })}
              </span>
            </>
          )}
        </p>
        <p className="games-muted">
          {t("gamification:games.challenge.finishers", { count: item.finishers })}
        </p>
      </div>
    </li>
  );
}

function Challenges() {
  const t = useT();
  const challenge = useChallenge();
  const items = challenge.data?.items ?? [];
  if (!items.length) return null;
  return (
    <section aria-labelledby="games-week">
      <h2 id="games-week">{t("gamification:games.week")}</h2>
      <ul className="games-challenges">
        {items.map((item) => (
          <ChallengeCard key={item.kind} item={item} />
        ))}
      </ul>
    </section>
  );
}

/** A game of the page: the whole tile opens it (its intro: alone or together). */
function GameTile({ game }: { game: HubGame }) {
  const t = useT();
  const format = useFormat();
  const quota = gamesLeft(game);
  const to =
    game.key === "cinemot"
      ? "/games/cinemot"
      : game.solo
        ? `/games/play/${game.key}`
        : `/games/party?game=${game.key}`;
  return (
    <li className="games-tile-card" data-game={game.key}>
      <RouterLink to={to}>
        <span className="games-tile-card__art" aria-hidden="true">
          <Icon name={GAME_ICONS[game.key] ?? "gamepad"} size={36} />
        </span>
        <span className="games-tile-card__body">
          <h3>{t(`gamification:games.game.${game.key}.name`)}</h3>
          <span className="games-tile-card__pitch">{t(`gamification:games.game.${game.key}.pitch`)}</span>
          <span className="games-tile-card__tags">
            {game.solo ? (
              <span>
                <Icon name="user" size={12} />
                {t("gamification:games.alone")}
              </span>
            ) : null}
            {game.party ? (
              <span>
                <Icon name="users" size={12} />
                {t("gamification:games.together")}
              </span>
            ) : null}
            {quota ? (
              <span className="games-tile-card__today" data-empty={quota.left === 0 || undefined}>
                <Icon name="clock" size={12} />
                {t("gamification:games.today.short", quota)}
              </span>
            ) : null}
            {game.best_week ? (
              <span className="games-tile-card__best">
                <Icon name="trophy" size={12} />
                {format.number(game.best_week)}
              </span>
            ) : null}
          </span>
        </span>
      </RouterLink>
    </li>
  );
}

function JoinBox() {
  const t = useT();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  return (
    <form
      className="games-join"
      onSubmit={(event) => {
        event.preventDefault();
        if (code.trim().length >= 4) navigate(`/games/party/${code.trim().toUpperCase()}?join=1`);
      }}
    >
      <label htmlFor="games-code">{t("gamification:games.party.code")}</label>
      <input
        id="games-code"
        value={code}
        maxLength={6}
        autoComplete="off"
        autoCapitalize="characters"
        placeholder="ABCD"
        onChange={(event) => setCode(event.target.value.replace(/[^a-zA-Z]/g, "").toUpperCase())}
      />
      <Button type="submit" variant="secondary" disabled={code.length < 4}>
        {t("gamification:games.party.join")}
      </Button>
    </form>
  );
}

/**
 * Issue 265: the games page — today (the wheel, the day's title, a reminder of the quests and
 * the running campaigns — issue 313 — the
 * week's challenge), the games to play
 * alone or together, the parties to join with their code, and each game's board.
 */
export default function GamesPage() {
  const t = useT();
  const hub = useGamesHub();
  const [boardGame, setBoardGame] = useState("poster");
  const games = hub.data?.games ?? [];
  const playable = games.filter((g) => g.key !== "challenge");
  return (
    <div className="games-page">
      <PageHeader
        title={t("gamification:games.title")}
        context={t("gamification:games.pitch")}
        icon="gamepad"
      />
      {hub.isPending ? (
        <Skeleton shape="tile" count={6} label={t("gamification:games.loading")} />
      ) : !hub.data?.enabled ? (
        <p className="games-muted">{t("gamification:games.off")}</p>
      ) : (
        <>
          <section className="games-today" aria-labelledby="games-today">
            <h2 id="games-today">{t("gamification:games.today")}</h2>
            <div className="games-today__grid">
              <Wheel />
              {games.some((g) => g.key === "cinemot") ? <Cinemot status={hub.data.cinemot} /> : null}
            </div>
            <div className="games-reminders">
              <QuestReminder />
              <CampaignReminders />
            </div>
          </section>

          {games.some((g) => g.key === "challenge") ? <Challenges /> : null}

          <section aria-labelledby="games-all">
            <h2 id="games-all">{t("gamification:games.all")}</h2>
            <ul className="games-grid">
              {playable.map((game) => (
                <GameTile key={game.key} game={game} />
              ))}
            </ul>
          </section>

          {hub.data.party ? (
            <section className="games-together" aria-labelledby="games-together">
              <span className="games-together__art" aria-hidden="true">
                <Icon name="party" size={36} />
              </span>
              <h2 id="games-together">{t("gamification:games.party.title")}</h2>
              <p className="games-muted">{t("gamification:games.party.pitch")}</p>
              <div className="games-together__row">
                <JoinBox />
                <Button asChild>
                  <RouterLink to="/games/party">
                    <Icon name="plus" size={16} />
                    {t("gamification:games.party.open")}
                  </RouterLink>
                </Button>
              </div>
              {hub.data.parties.length ? (
                <ul className="games-parties">
                  {hub.data.parties.map((party) => (
                    <li key={party.code}>
                      <RouterLink to={`/games/party/${party.code}`}>
                        <b>{party.code}</b> · {t(`gamification:games.game.${party.game}.name`)} ·{" "}
                        {t(`gamification:games.party.status.${party.status}`)}
                        {party.host ? ` · ${t("gamification:games.party.hosting")}` : ""}
                      </RouterLink>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          <section aria-labelledby="games-boards">
            <h2 id="games-boards">{t("gamification:games.boards")}</h2>
            <label className="games-board-pick">
              <span>{t("gamification:games.boardOf")}</span>
              <select value={boardGame} onChange={(event) => setBoardGame(event.target.value)}>
                {[...games.map((g) => g.key), ...(hub.data.party ? ["party"] : [])].map((key) => (
                  <option key={key} value={key}>
                    {key === "party"
                      ? t("gamification:games.party.wins")
                      : t(`gamification:games.game.${key}.name`)}
                  </option>
                ))}
              </select>
            </label>
            <Board key={boardGame} game={boardGame} />
          </section>
        </>
      )}
    </div>
  );
}
