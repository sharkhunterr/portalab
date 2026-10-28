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
import type { WidgetPayload } from "../dashboard/api";
import { WheelWidget } from "../gamification/wheel/WheelWidget";
import { imageUrl } from "../media/api";
import { type ChallengeItem, GAME_ICONS, type HubGame, useChallenge, useGamesHub } from "./api";
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
    <article className="games-today__card" data-state={state}>
      <h3>
        <Icon name="type" size={18} />
        {t("gamification:games.game.cinemot.name")}
      </h3>
      <p>{t(`gamification:games.cinemot.state.${state}`)}</p>
      <Button asChild variant={state === "new" || state === "playing" ? "primary" : "secondary"}>
        <RouterLink to="/games/cinemot">
          {state === "won" || state === "lost"
            ? t("gamification:games.cinemot.see")
            : t("gamification:games.play")}
        </RouterLink>
      </Button>
    </article>
  );
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
  return (
    <article className="games-today__card games-challenge" data-done={item.done || undefined}>
      <h3>
        <Icon name={CHALLENGE_ICONS[item.kind] ?? "gamepad"} size={18} />
        {t(`gamification:games.challenge.kind.${item.kind}`)}
      </h3>
      <div className="games-challenge__game">
        {item.title.image_id ? (
          <img src={imageUrl(item.title.image_id) ?? ""} alt="" />
        ) : (
          <Icon name={CHALLENGE_ICONS[item.kind] ?? "gamepad"} size={40} />
        )}
        <div>
          <RouterLink to={`/media/${item.title.id}`}>
            <b>{item.title.title}</b>
          </RouterLink>
          {item.title.platform ? <span className="games-muted">{item.title.platform}</span> : null}
          <span>{t(`gamification:games.challenge.goal.${item.unit}`, { target: item.target })}</span>
        </div>
      </div>
      <div
        className="games-progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={item.target}
        aria-valuenow={item.mine}
      >
        <span style={{ inlineSize: `${share * 100}%` }} />
      </div>
      <p className="games-muted">
        {item.done
          ? t("gamification:games.challenge.done")
          : t(`gamification:games.challenge.progress.${item.unit}`, {
              mine: format.number(item.mine),
              target: item.target,
              until: format.date(item.ends_at),
            })}
      </p>
      <p className="games-muted">{t("gamification:games.challenge.finishers", { count: item.finishers })}</p>
    </article>
  );
}

function Challenges() {
  const challenge = useChallenge();
  return (
    <>
      {(challenge.data?.items ?? []).map((item) => (
        <ChallengeCard key={item.kind} item={item} />
      ))}
    </>
  );
}

function GameTile({ game }: { game: HubGame }) {
  const t = useT();
  const format = useFormat();
  const to = game.key === "cinemot" ? "/games/cinemot" : `/games/play/${game.key}`;
  return (
    <li className="games-tile-card" data-game={game.key}>
      <span className="games-tile-card__icon" aria-hidden="true">
        <Icon name={GAME_ICONS[game.key] ?? "gamepad"} size={28} />
      </span>
      <h3>{t(`gamification:games.game.${game.key}.name`)}</h3>
      <p>{t(`gamification:games.game.${game.key}.pitch`)}</p>
      {game.best_week ? (
        <span className="games-tile-card__best">
          <Icon name="trophy" size={14} />
          {t("gamification:games.bestWeek", { score: format.number(game.best_week) })}
        </span>
      ) : null}
      <div className="games-tile-card__actions">
        {game.solo ? (
          <Button asChild size="md">
            <RouterLink to={to}>
              <Icon name="play" size={16} />
              {t("gamification:games.play")}
            </RouterLink>
          </Button>
        ) : null}
        {game.party ? (
          <Button asChild variant="secondary">
            <RouterLink to={`/games/party?game=${game.key}`}>
              <Icon name="users" size={16} />
              {t("gamification:games.together")}
            </RouterLink>
          </Button>
        ) : null}
      </div>
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
      <Button type="submit" disabled={code.length < 4}>
        {t("gamification:games.party.join")}
      </Button>
    </form>
  );
}

/**
 * Issue 265: the games page — today (the wheel, the day's title, the week's challenge), the games to play
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
              {games.some((g) => g.key === "challenge") ? <Challenges /> : null}
            </div>
          </section>

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
              <h2 id="games-together">{t("gamification:games.party.title")}</h2>
              <p className="games-muted">{t("gamification:games.party.pitch")}</p>
              <div className="games-together__row">
                <JoinBox />
                <Button asChild variant="secondary">
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
