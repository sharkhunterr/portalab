import { useMemo } from "react";
import { Link as RouterLink, useParams, useSearchParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { Skeleton } from "../../design-system/components/Placeholders";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import {
  GAME_ICONS,
  gamesLeft,
  type SoloView,
  skewOf,
  useGamesHub,
  useSession,
  useSessionAction,
  useStart,
} from "./api";
import { Board } from "./Boards";
import { MemoryBoard } from "./MemoryBoard";
import { QuestionView, RevealView } from "./QuestionView";
import "./games.css";

/** The rounds played, one step each: right, missed, the one being played, those to come. */
function Steps({ view }: { view: SoloView }) {
  const sudden = view.game === "higher_lower";
  const count = sudden ? view.results.length + (view.status === "playing" ? 1 : 0) : view.rounds;
  return (
    <ol className="games-steps" aria-hidden="true" data-sudden={sudden || undefined}>
      {Array.from({ length: Math.min(count, 40) }, (_, at) => {
        const result = view.results[at];
        const state = result
          ? result.correct
            ? "right"
            : "wrong"
          : at === view.results.length && view.status === "playing" && view.phase !== "reveal"
            ? "now"
            : undefined;
        // biome-ignore lint/suspicious/noArrayIndexKey: the rounds in their order
        return <li key={at} data-state={state} />;
      })}
    </ol>
  );
}

/** While a game is played: what it is, the question it is at, the points, a way out. */
function GameBar({ view }: { view: SoloView }) {
  const t = useT();
  const format = useFormat();
  return (
    <header className="games-bar" data-game={view.game}>
      <Button asChild variant="ghost" size="icon">
        <RouterLink to="/games" aria-label={t("gamification:games.quit")}>
          <Icon name="close" size={18} />
        </RouterLink>
      </Button>
      <span className="games-bar__icon" aria-hidden="true">
        <Icon name={GAME_ICONS[view.game] ?? "gamepad"} size={18} />
      </span>
      <div className="games-bar__title">
        <h1>{t(`gamification:games.game.${view.game}.name`)}</h1>
        {view.status === "playing" && view.game !== "memory" ? (
          <span>
            {view.game === "higher_lower"
              ? t("gamification:games.streak", { count: view.correct })
              : t("gamification:games.round", { round: view.round ?? 1, rounds: view.rounds })}
          </span>
        ) : null}
      </div>
      <b className="games-bar__score">
        <Icon name="star" size={14} />
        {format.number(view.score)}
      </b>
    </header>
  );
}

/** Issue 270: the games of the day left, or that there are none — the way back is tomorrow. */
function Today({ game }: { game: string }) {
  const t = useT();
  const hub = useGamesHub();
  const quota = gamesLeft(hub.data?.games.find((g) => g.key === game));
  if (!quota) return null;
  if (quota.left === 0)
    return (
      <p className="games-today-none" role="status">
        <Icon name="clock" size={16} />
        {t("gamification:games.today.none", { max: quota.max })}
      </p>
    );
  return <p className="games-muted">{t("gamification:games.today.left", quota)}</p>;
}

function useNoneLeft(game: string): boolean {
  const hub = useGamesHub();
  return gamesLeft(hub.data?.games.find((g) => g.key === game))?.left === 0;
}

function Over({ view, onAgain, busy }: { view: SoloView; onAgain: () => void; busy: boolean }) {
  const t = useT();
  const format = useFormat();
  const noneLeft = useNoneLeft(view.game);
  const sudden = view.game === "higher_lower";
  return (
    <section className="games-over" data-game={view.game}>
      <div className="games-over__card">
        <span className="games-over__badge" aria-hidden="true">
          <Icon name="trophy" size={40} />
        </span>
        <p className="games-over__label">{t("gamification:games.final")}</p>
        <p className="games-over__score">{format.number(view.score)}</p>
        <p>
          {sudden
            ? t("gamification:games.streak", { count: view.correct })
            : t("gamification:games.correctOf", { correct: view.correct, rounds: view.rounds })}
        </p>
        <Steps view={view} />
        {view.last?.reveal ? <RevealView reveal={view.last.reveal} mine={null} played={false} /> : null}
        <Today game={view.game} />
        <div className="games-actions">
          <Button disabled={busy || noneLeft} onClick={onAgain}>
            <Icon name="retry" size={16} />
            {t("gamification:games.again")}
          </Button>
          <Button asChild variant="secondary">
            <RouterLink to="/games">{t("gamification:games.back")}</RouterLink>
          </Button>
        </div>
      </div>
      <Board game={view.game} />
    </section>
  );
}

function Playing({ view, onAgain, busy }: { view: SoloView; onAgain: () => void; busy: boolean }) {
  const t = useT();
  const act = useSessionAction(view.id);
  const skew = useMemo(() => skewOf(view.now), [view.now]);
  if (view.status === "done") return <Over view={view} onAgain={onAgain} busy={busy} />;
  if (!view.question) return null;
  const revealed = view.phase === "reveal";
  return (
    <div className="games-play" data-game={view.game}>
      <Steps view={view} />
      <QuestionView
        key={view.round}
        question={view.question}
        base={`/api/v1/games/sessions/${view.id}`}
        round={view.round}
        started={view.started}
        seconds={view.seconds ?? 20}
        skew={skew}
        phase={view.phase ?? "question"}
        given={view.result?.given}
        answer={view.result?.answer}
        reveal={view.result?.reveal}
        mine={view.result}
        busy={act.isPending}
        onAnswer={(a) => act.mutate({ kind: "answer", ...a })}
        onTimeout={() => act.mutate({ kind: "answer" })}
      />
      {revealed && view.result?.reveal ? (
        <div className="games-after" data-correct={view.result.correct ? "true" : "false"}>
          <RevealView reveal={view.result.reveal} mine={view.result} played />
          <Button autoFocus disabled={act.isPending} onClick={() => act.mutate({ kind: "next" })}>
            {t("gamification:games.next")}
            <Icon name="chevron-right" size={16} />
          </Button>
        </div>
      ) : null}
      {act.error ? <p className="games-error">{act.error.message}</p> : null}
    </div>
  );
}

/** Before a game: what it is, how it goes (its questions, its time), to play it alone or together. */
function Intro({ game, onStart, busy }: { game: string; onStart: () => void; busy: boolean }) {
  const t = useT();
  const hub = useGamesHub();
  const info = hub.data?.games.find((g) => g.key === game);
  const solo = info?.solo ?? true;
  const quota = gamesLeft(info);
  return (
    <section className="games-hero" data-game={game}>
      <div className="games-hero__art" aria-hidden="true">
        <Icon name={GAME_ICONS[game] ?? "gamepad"} size={56} />
      </div>
      <div className="games-hero__body">
        <h2>{t(`gamification:games.game.${game}.name`)}</h2>
        <p className="games-hero__pitch">{t(`gamification:games.game.${game}.pitch`)}</p>
        <p>{t(`gamification:games.game.${game}.rules`)}</p>
        {info && (info.rounds || info.seconds || quota) ? (
          <ul className="games-facts">
            {game === "higher_lower" ? (
              <li>
                <Icon name="flame" size={14} />
                {t("gamification:games.facts.sudden")}
              </li>
            ) : info.rounds ? (
              <li>
                <Icon name="list" size={14} />
                {t("gamification:games.facts.rounds", { count: info.rounds })}
              </li>
            ) : null}
            {info.seconds ? (
              <li>
                <Icon name="clock" size={14} />
                {t("gamification:games.facts.seconds", { seconds: info.seconds })}
              </li>
            ) : null}
            {info.party ? (
              <li>
                <Icon name="users" size={14} />
                {t("gamification:games.facts.together")}
              </li>
            ) : null}
            {quota && quota.left > 0 ? (
              <li>
                <Icon name="calendar" size={14} />
                {t("gamification:games.today.left", quota)}
              </li>
            ) : null}
          </ul>
        ) : null}
        {quota?.left === 0 ? (
          <p className="games-today-none" role="status">
            <Icon name="clock" size={16} />
            {t("gamification:games.today.none", { max: quota.max })}
          </p>
        ) : null}
        <div className="games-actions">
          {solo ? (
            <Button className="games-hero__start" disabled={busy || quota?.left === 0} onClick={onStart}>
              <Icon name="play" size={18} />
              {t("gamification:games.start")}
            </Button>
          ) : null}
          {info?.party ? (
            <Button asChild variant="secondary">
              <RouterLink to={`/games/party?game=${game}`}>
                <Icon name="users" size={16} />
                {t("gamification:games.together")}
              </RouterLink>
            </Button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

/** Issue 265: a game played alone — its intro, then question after question, then its score and board. */
export default function SoloPage() {
  const t = useT();
  const { game = "poster" } = useParams();
  const [search, setSearch] = useSearchParams();
  const id = search.get("session") ?? undefined;
  const session = useSession(id);
  const start = useStart();
  const noneLeft = useNoneLeft(game);
  const begin = () =>
    start.mutate(game, { onSuccess: (view) => setSearch({ session: view.id }, { replace: Boolean(id) }) });
  const view = session.data;
  if (id && view && game !== "memory") {
    // a game under way: the whole page to it, below a bar that says where one is
    return (
      <div className="games-page games-page--playing">
        <GameBar view={view} />
        <Playing view={view} onAgain={begin} busy={start.isPending} />
        {start.error ? <p className="games-error">{start.error.message}</p> : null}
      </div>
    );
  }
  return (
    <div className="games-page">
      <PageHeader title={t(`gamification:games.game.${game}.name`)} icon={GAME_ICONS[game] ?? "gamepad"} />
      {!id ? (
        <>
          <Intro game={game} onStart={begin} busy={start.isPending} />
          {start.error ? <p className="games-error">{start.error.message}</p> : null}
          <Board game={game} />
        </>
      ) : session.isPending ? (
        <Skeleton shape="card" label={t("gamification:games.loading")} />
      ) : !view ? (
        <p className="games-error">{t("gamification:games.gone")}</p>
      ) : (
        <MemoryBoard view={view} onAgain={noneLeft ? undefined : begin} />
      )}
    </div>
  );
}
