import { useEffect, useRef, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { BLUR_STEPS, metadataImage, type Question, type Result, type Reveal } from "./api";

/** The time left of a round, by the server's clock (``skew``: the server's against mine). */
export function useRemaining(started: string | undefined, seconds: number, skew: number, running: boolean) {
  const [now, setNow] = useState(() => Date.now() + skew);
  useEffect(() => {
    if (!running) return undefined;
    const timer = window.setInterval(() => setNow(Date.now() + skew), 200);
    return () => window.clearInterval(timer);
  }, [running, skew]);
  const start = started ? new Date(started).getTime() : now;
  return {
    left: Math.max(0, start + seconds * 1000 - now),
    before: Math.max(0, start - now), // the party's countdown
    elapsed: Math.max(0, now - start),
  };
}

function TimerBar({ left, seconds }: { left: number; seconds: number }) {
  const t = useT();
  const share = Math.max(0, Math.min(1, left / (seconds * 1000)));
  return (
    <div
      className="games-timer"
      role="timer"
      aria-label={t("gamification:games.timeLeft", { seconds: Math.ceil(left / 1000) })}
    >
      <span className="games-timer__bar">
        <span style={{ inlineSize: `${share * 100}%` }} data-low={share < 0.25 || undefined} />
      </span>
      <b>{Math.ceil(left / 1000)}</b>
    </div>
  );
}

function PosterPrompt({
  base,
  elapsed,
  seconds,
  revealed,
}: {
  base: string;
  elapsed: number;
  seconds: number;
  revealed: boolean;
}) {
  const t = useT();
  const step = revealed
    ? BLUR_STEPS - 1
    : Math.min(BLUR_STEPS - 2, Math.floor(elapsed / ((seconds * 1000) / (BLUR_STEPS - 1))));
  return (
    <div className="games-poster">
      <img src={`${base}/image?step=${step}`} alt={t("gamification:games.posterAlt")} />
    </div>
  );
}

function AudioPrompt({ base, revealed }: { base: string; revealed: boolean }) {
  const t = useT();
  const audio = useRef<HTMLAudioElement>(null);
  const [blocked, setBlocked] = useState(false);
  useEffect(() => {
    const element = audio.current;
    if (!element) return;
    element.play().catch(() => setBlocked(true));
  }, []);
  useEffect(() => {
    if (revealed) audio.current?.pause();
  }, [revealed]);
  return (
    <div className="games-audio">
      <Icon name="music" size={48} />
      {/* biome-ignore lint/a11y/useMediaCaption: a theme tune to guess, no words */}
      <audio ref={audio} src={`${base}/audio`} preload="auto" controls={blocked} />
      {blocked ? (
        <Button
          variant="secondary"
          onClick={() => {
            setBlocked(false);
            void audio.current?.play();
          }}
        >
          <Icon name="play" size={16} />
          {t("gamification:games.listen")}
        </Button>
      ) : (
        <p className="games-muted">{t("gamification:games.listening")}</p>
      )}
    </div>
  );
}

function Prompt({
  question,
  base,
  elapsed,
  seconds,
  revealed,
}: {
  question: Question;
  base: string;
  elapsed: number;
  seconds: number;
  revealed: boolean;
}) {
  const t = useT();
  const prompt = question.prompt;
  let ask: string;
  if (question.game === "higher_lower")
    ask = t(`gamification:games.ask.higher_lower.${prompt.criterion ?? "rating"}`);
  else if (question.game === "memories")
    ask = t(`gamification:games.ask.memories.${prompt.question ?? "first"}`);
  else if (question.game === "whowatched")
    ask = t("gamification:games.ask.whowatched", { title: prompt.title ?? "", year: prompt.year ?? "" });
  else ask = t(`gamification:games.ask.${question.game}`);
  return (
    <div className="games-prompt">
      <p className="games-ask">{ask}</p>
      {question.image ? (
        <PosterPrompt base={base} elapsed={elapsed} seconds={seconds} revealed={revealed} />
      ) : null}
      {question.audio ? <AudioPrompt base={base} revealed={revealed} /> : null}
      {prompt.people?.length ? (
        <ul className="games-people">
          {prompt.people.map((person) => (
            <li key={person.name}>
              {person.image ? (
                <img src={metadataImage(person.image, "w185") ?? ""} alt="" />
              ) : (
                <Icon name="user" size={40} />
              )}
              <span>{person.name}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {prompt.text ? <blockquote className="games-synopsis">{prompt.text}</blockquote> : null}
    </div>
  );
}

function shown(
  value: string | number | null | undefined,
  criterion: string | undefined,
  format: ReturnType<typeof useFormat>,
): string {
  if (value == null) return "";
  if (criterion === "rating") return `${format.number(Math.round(Number(value) * 10) / 10)}/10`;
  if (criterion === "runtime")
    return `${Math.floor(Number(value) / 60)} h ${String(Number(value) % 60).padStart(2, "0")}`;
  if (typeof value === "string" && value.length === 10) return format.date(value);
  return String(value);
}

/** What the round was: right or not, the points, the answer — and the title it was. */
export function RevealView({
  reveal,
  mine,
  played,
}: {
  reveal: Reveal;
  mine: Result | null | undefined;
  played: boolean;
}) {
  const t = useT();
  const poster = metadataImage(reveal.poster, "w185");
  return (
    <div className="games-reveal" data-correct={mine?.correct ? "true" : played ? "false" : undefined}>
      {played ? (
        <p className="games-reveal__verdict">
          <Icon name={mine?.correct ? "check" : "close"} size={20} />
          {mine?.correct
            ? t("gamification:games.right", { points: mine.points })
            : mine
              ? t("gamification:games.wrong", { points: mine.points })
              : t("gamification:games.tooLate")}
        </p>
      ) : null}
      {reveal.title ? (
        <div className="games-reveal__title">
          {poster ? <img src={poster} alt="" /> : null}
          <span>
            {reveal.who ? <b>{reveal.who} · </b> : null}
            {reveal.title}
            {reveal.year ? ` (${reveal.year})` : ""}
          </span>
        </div>
      ) : null}
    </div>
  );
}

/** Titles to put in order: tapped one after the other, then sent. */
function Ordering({
  question,
  onAnswer,
  disabled,
  answer,
  values,
}: {
  question: Question;
  onAnswer?: ((order: string[]) => void) | undefined;
  disabled: boolean;
  answer?: string[] | undefined;
  values?: Record<string, string | number | null> | undefined;
}) {
  const t = useT();
  const [order, setOrder] = useState<string[]>([]);
  const shown = answer ?? order;
  const rest = question.choices.filter((c) => !shown.includes(c.id));
  const byId = Object.fromEntries(question.choices.map((c) => [c.id, c]));
  return (
    <div className="games-order">
      <ol className="games-order__picked">
        {shown.map((id, at) => (
          <li
            key={id}
            data-right={answer && order.length ? (order[at] === id ? "true" : "false") : undefined}
          >
            <span className="games-order__rank">{at + 1}</span>
            {byId[id]?.image ? <img src={metadataImage(byId[id]?.image, "w92") ?? ""} alt="" /> : null}
            <span>{byId[id]?.label}</span>
            {values?.[id] != null ? <b>{values[id]}</b> : null}
          </li>
        ))}
      </ol>
      {!answer ? (
        <>
          <div className="games-choices" data-layout="posters">
            {rest.map((choice) => (
              <button
                key={choice.id}
                type="button"
                className="games-choice"
                disabled={disabled}
                onClick={() => setOrder([...order, choice.id])}
              >
                {choice.image ? <img src={metadataImage(choice.image, "w185") ?? ""} alt="" /> : null}
                <span>{choice.label}</span>
              </button>
            ))}
          </div>
          <div className="games-actions">
            <Button
              variant="ghost"
              disabled={disabled || !order.length}
              onClick={() => setOrder(order.slice(0, -1))}
            >
              <Icon name="undo" size={16} />
              {t("gamification:games.undo")}
            </Button>
            <Button disabled={disabled || rest.length > 0} onClick={() => onAnswer?.(order)}>
              <Icon name="check" size={16} />
              {t("gamification:games.send")}
            </Button>
          </div>
        </>
      ) : null}
    </div>
  );
}

/**
 * Issue 265: a question of a game, alone or in a party — its prompt (a poster as blurred as its time says, a
 * theme tune, actors, a synopsis), its choices, its time; then what it was. The answer is the server's to
 * check: the page sends a choice (or an order) and is told.
 */
export function QuestionView({
  question,
  base,
  started,
  seconds,
  skew,
  phase,
  given,
  answer,
  reveal,
  mine,
  onAnswer,
  onTimeout,
  busy = false,
  screen = false,
}: {
  question: Question;
  base: string;
  started: string | undefined;
  seconds: number;
  skew: number;
  phase: "question" | "reveal";
  given?: unknown;
  answer?: string | string[] | undefined;
  reveal?: Reveal | undefined;
  mine?: Result | null | undefined;
  onAnswer?: ((a: { choice?: string; order?: string[] }) => void) | undefined;
  /** the time is up without an answer (a game alone tells the server: nothing given) */
  onTimeout?: (() => void) | undefined;
  busy?: boolean | undefined;
  screen?: boolean | undefined;
}) {
  const format = useFormat();
  const revealed = phase === "reveal";
  const { left, elapsed } = useRemaining(started, seconds, skew, !revealed);
  const answered = given != null;
  const disabled = busy || answered || revealed || !onAnswer || left <= 0;
  const timedOut = useRef(false);
  useEffect(() => {
    if (left > 0 || answered || revealed || timedOut.current || !onTimeout) return;
    timedOut.current = true;
    onTimeout();
  }, [left, answered, revealed, onTimeout]);
  const criterion = question.prompt.criterion;
  const values = reveal?.values
    ? Object.fromEntries(
        Object.entries(reveal.values).map(([id, value]) => [
          id,
          shown(value, question.game === "timeline" ? "year" : criterion, format),
        ]),
      )
    : undefined;
  const posters = question.choices.some((c) => c.image);
  return (
    <section className="games-question" data-screen={screen || undefined} aria-live="polite">
      {!revealed ? <TimerBar left={left} seconds={seconds} /> : null}
      <Prompt question={question} base={base} elapsed={elapsed} seconds={seconds} revealed={revealed} />
      {question.ordered ? (
        <Ordering
          key={`${base}:${question.choices.map((c) => c.id).join()}`}
          question={question}
          disabled={disabled}
          onAnswer={(order) => onAnswer?.({ order })}
          answer={revealed && Array.isArray(answer) ? answer : undefined}
          values={values}
        />
      ) : (
        <div className="games-choices" data-layout={posters ? "posters" : "list"}>
          {question.choices.map((choice) => {
            const state = revealed
              ? choice.id === answer
                ? "right"
                : choice.id === given || choice.id === mine?.given
                  ? "wrong"
                  : undefined
              : choice.id === given
                ? "given"
                : undefined;
            return (
              <button
                key={choice.id}
                type="button"
                className="games-choice"
                data-state={state}
                disabled={disabled}
                onClick={() => onAnswer?.({ choice: choice.id })}
              >
                {choice.image ? <img src={metadataImage(choice.image, "w342") ?? ""} alt="" /> : null}
                <span>{choice.label}</span>
                {values?.[choice.id] ? <b className="games-choice__value">{values[choice.id]}</b> : null}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
