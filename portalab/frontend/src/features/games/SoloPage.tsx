import { useMemo } from "react";
import { Link as RouterLink, useParams, useSearchParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { Skeleton } from "../../design-system/components/Placeholders";
import { useT } from "../../i18n/hooks/useT";
import { GAME_ICONS, type SoloView, skewOf, useSession, useSessionAction, useStart } from "./api";
import { Board } from "./Boards";
import { MemoryBoard } from "./MemoryBoard";
import { QuestionView, RevealView } from "./QuestionView";
import "./games.css";

function Results({ view }: { view: SoloView }) {
  return (
    <ol className="games-dots" aria-hidden="true">
      {view.results.map((r, at) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: the rounds in their order
        <li key={at} data-correct={r.correct ? "true" : "false"} />
      ))}
    </ol>
  );
}

function Playing({ view, onAgain }: { view: SoloView; onAgain: () => void }) {
  const t = useT();
  const act = useSessionAction(view.id);
  const skew = useMemo(() => skewOf(view.now), [view.now]);
  if (view.status === "done") {
    const sudden = view.game === "higher_lower";
    return (
      <section className="games-over">
        <Icon name="trophy" size={48} />
        <h2>{t("gamification:games.score", { score: view.score })}</h2>
        <p>
          {sudden
            ? t("gamification:games.streak", { count: view.correct })
            : t("gamification:games.correctOf", { correct: view.correct, rounds: view.rounds })}
        </p>
        <Results view={view} />
        {view.last?.reveal ? <RevealView reveal={view.last.reveal} mine={null} played={false} /> : null}
        <div className="games-actions">
          <Button onClick={onAgain}>
            <Icon name="retry" size={16} />
            {t("gamification:games.again")}
          </Button>
          <Button asChild variant="secondary">
            <RouterLink to="/games">{t("gamification:games.back")}</RouterLink>
          </Button>
        </div>
        <Board game={view.game} />
      </section>
    );
  }
  if (!view.question) return null;
  const revealed = view.phase === "reveal";
  return (
    <>
      <div className="games-status">
        <span>{t("gamification:games.round", { round: view.round ?? 1, rounds: view.rounds })}</span>
        <b>{t("gamification:games.points", { score: view.score })}</b>
      </div>
      <QuestionView
        key={view.round}
        question={view.question}
        base={`/api/v1/games/sessions/${view.id}`}
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
        <div className="games-after">
          <RevealView reveal={view.result.reveal} mine={view.result} played />
          <Button autoFocus disabled={act.isPending} onClick={() => act.mutate({ kind: "next" })}>
            {t("gamification:games.next")}
            <Icon name="chevron-right" size={16} />
          </Button>
        </div>
      ) : null}
      {act.error ? <p className="games-error">{act.error.message}</p> : null}
    </>
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
  const begin = () =>
    start.mutate(game, { onSuccess: (view) => setSearch({ session: view.id }, { replace: Boolean(id) }) });
  const view = session.data;
  return (
    <div className="games-page">
      <PageHeader
        title={t(`gamification:games.game.${game}.name`)}
        context={t(`gamification:games.game.${game}.pitch`)}
        icon={GAME_ICONS[game] ?? "gamepad"}
      />
      {!id ? (
        <section className="games-intro">
          <p>{t(`gamification:games.game.${game}.rules`)}</p>
          <div className="games-actions">
            <Button disabled={start.isPending} onClick={begin}>
              <Icon name="play" size={16} />
              {t("gamification:games.start")}
            </Button>
            <Button asChild variant="secondary">
              <RouterLink to="/games">{t("gamification:games.back")}</RouterLink>
            </Button>
          </div>
          {start.error ? <p className="games-error">{start.error.message}</p> : null}
          <Board game={game} />
        </section>
      ) : session.isPending ? (
        <Skeleton shape="card" label={t("gamification:games.loading")} />
      ) : !view ? (
        <p className="games-error">{t("gamification:games.gone")}</p>
      ) : game === "memory" ? (
        <MemoryBoard view={view} onAgain={begin} />
      ) : (
        <Playing view={view} onAgain={begin} />
      )}
    </div>
  );
}
