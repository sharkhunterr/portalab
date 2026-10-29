import { type CSSProperties, useEffect, useLayoutEffect, useRef, useState } from "react";
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
  const low = share < 0.25 || undefined;
  return (
    <div
      className="games-timer"
      role="timer"
      data-low={low}
      aria-label={t("gamification:games.timeLeft", { seconds: Math.ceil(left / 1000) })}
    >
      <span className="games-timer__bar">
        <span style={{ inlineSize: `${share * 100}%` }} />
      </span>
      <b>
        <Icon name="clock" size={14} />
        {Math.ceil(left / 1000)}
      </b>
    </div>
  );
}

function PosterPrompt({
  base,
  round,
  elapsed,
  seconds,
  revealed,
}: {
  base: string;
  round: number;
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
      {/* the round in the address: each question's image is its own, never the browser's last one */}
      <img src={`${base}/image?round=${round}&step=${step}`} alt={t("gamification:games.posterAlt")} />
    </div>
  );
}

/** Plays, or says the browser would not (no sound before a tap, on a phone). */
function play(element: HTMLAudioElement, blocked: () => void) {
  try {
    element.play()?.catch(blocked);
  } catch {
    blocked();
  }
}

/** A theme tune to recognise: a turning record while it plays, a button to pause it or hear it again. */
function AudioPrompt({ base, round, revealed }: { base: string; round: number; revealed: boolean }) {
  const t = useT();
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [blocked, setBlocked] = useState(false);
  useEffect(() => {
    const element = audio.current;
    if (!element) return;
    play(element, () => setBlocked(true));
  }, []);
  useEffect(() => {
    if (revealed) audio.current?.pause();
  }, [revealed]);
  const toggle = () => {
    const element = audio.current;
    if (!element) return;
    setBlocked(false);
    if (element.paused) play(element, () => setBlocked(true));
    else element.pause();
  };
  const again = () => {
    const element = audio.current;
    if (!element) return;
    element.currentTime = 0;
    setBlocked(false);
    play(element, () => setBlocked(true));
  };
  return (
    <div className="games-audio" data-playing={playing || undefined}>
      <span className="games-audio__disc" aria-hidden="true">
        <Icon name="music" size={28} />
      </span>
      <span className="games-audio__bars" aria-hidden="true">
        <i />
        <i />
        <i />
        <i />
        <i />
      </span>
      {/* biome-ignore lint/a11y/useMediaCaption: a theme tune to guess, no words */}
      <audio
        ref={audio}
        src={`${base}/audio?round=${round}`}
        preload="auto"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
      />
      <div className="games-actions">
        <Button variant={blocked ? "primary" : "secondary"} onClick={toggle}>
          <Icon name={playing ? "pause" : "play"} size={16} />
          {playing ? t("gamification:games.pause") : t("gamification:games.listen")}
        </Button>
        <Button variant="ghost" onClick={again}>
          <Icon name="replay" size={16} />
          {t("gamification:games.replay")}
        </Button>
      </div>
      <p className="games-muted">
        {blocked ? t("gamification:games.tapToListen") : t("gamification:games.listening")}
      </p>
    </div>
  );
}

function Prompt({
  question,
  base,
  round,
  elapsed,
  seconds,
  revealed,
}: {
  question: Question;
  base: string;
  round: number;
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
        <PosterPrompt base={base} round={round} elapsed={elapsed} seconds={seconds} revealed={revealed} />
      ) : null}
      {question.audio ? <AudioPrompt base={base} round={round} revealed={revealed} /> : null}
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

const LETTERS = "ABCDEFGHI";

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
      {poster ? <img className="games-reveal__poster" src={poster} alt="" /> : null}
      <div className="games-reveal__text">
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
          <p className="games-reveal__title">
            {reveal.who ? <b>{reveal.who} · </b> : null}
            {reveal.title}
            {reveal.year ? <span className="games-muted"> ({reveal.year})</span> : null}
          </p>
        ) : null}
      </div>
    </div>
  );
}

interface Drag {
  id: string;
  from: number;
  to: number;
  dy: number;
  step: number;
}

/**
 * Issue 269: titles to put in order on a timeline, the oldest at the top — dragged into place (a mouse, a
 * finger) or moved a place up or down by their arrows; sent with « Send », or as they are when the time runs
 * out. Once answered, the right timeline with each title's year, and where I had put those out of place.
 */
function Ordering({
  question,
  onAnswer,
  onArrange,
  disabled,
  answer,
  given,
  values,
}: {
  question: Question;
  onAnswer?: ((order: string[]) => void) | undefined;
  /** the order as it stands, and whether the member moved anything (what the time running out sends) */
  onArrange?: ((order: string[], touched: boolean) => void) | undefined;
  disabled: boolean;
  answer?: string[] | undefined;
  given?: string[] | undefined;
  values?: Record<string, string | number | null> | undefined;
}) {
  const t = useT();
  const [order, setOrder] = useState<string[]>(() => question.choices.map((c) => c.id));
  const [drag, setDrag] = useState<Drag | null>(null);
  const [said, setSaid] = useState("");
  const touched = useRef(false);
  const start = useRef<{ y: number; centers: number[] }>({ y: 0, centers: [] });
  const nodes = useRef(new Map<string, HTMLLIElement>());
  const tops = useRef(new Map<string, number>());
  const byId = Object.fromEntries(question.choices.map((c) => [c.id, c]));
  const mine = given?.length ? given : touched.current ? order : undefined;
  const shown = answer ?? order;
  const fixed = Boolean(answer) || disabled;

  // a title that changed place glides to it (its arrows, a drop, the right timeline once answered): from
  // where it was seen — its place in the list, and how far a drag had moved it — to its new place; only when
  // the order changed (the time's ticks and an image loading move nothing)
  const seen = useRef("");
  const shifts = useRef(new Map<string, number>());
  useLayoutEffect(() => {
    const key = shown.join();
    const changed = key !== seen.current;
    seen.current = key;
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    for (const [id, node] of nodes.current) {
      const top = node.offsetTop;
      const before = tops.current.get(id);
      tops.current.set(id, top + (shifts.current.get(id) ?? 0));
      if (!changed || drag || still || before == null || Math.abs(before - top) < 1 || !node.animate)
        continue;
      node.animate([{ transform: `translateY(${before - top}px)` }, { transform: "none" }], {
        duration: 240,
        easing: "cubic-bezier(.2,.8,.2,1)",
      });
    }
  });

  const move = (from: number, to: number) => {
    if (from === to || to < 0 || to >= order.length) return;
    const next = [...order];
    const [id] = next.splice(from, 1);
    if (!id) return;
    next.splice(to, 0, id);
    touched.current = true;
    setOrder(next);
    onArrange?.(next, true);
    setSaid(t("gamification:games.order.moved", { title: byId[id]?.label ?? "", place: to + 1 }));
  };

  const grab = (event: React.PointerEvent<HTMLLIElement>, id: string, at: number) => {
    if (fixed || event.button !== 0) return;
    if (event.target instanceof Element && event.target.closest("button")) return;
    const boxes = order.map((key) => nodes.current.get(key)?.getBoundingClientRect());
    const box = boxes[at];
    if (!box) return;
    const after = boxes[at + 1] ?? boxes[at - 1];
    const gap = after ? Math.abs((boxes[at + 1] ? after.top - box.bottom : box.top - after.bottom) || 0) : 0;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    start.current = { y: event.clientY, centers: boxes.map((b) => (b ? b.top + b.height / 2 : 0)) };
    setDrag({ id, from: at, to: at, dy: 0, step: box.height + gap });
  };
  const follow = (event: React.PointerEvent<HTMLLIElement>) => {
    if (!drag) return;
    const dy = event.clientY - start.current.y;
    const center = (start.current.centers[drag.from] ?? 0) + dy;
    const to = start.current.centers.filter((c, i) => i !== drag.from && c < center).length;
    setDrag({ ...drag, dy, to });
  };
  const drop = () => {
    if (!drag) return;
    setDrag(null);
    move(drag.from, drag.to);
  };
  const shift = (at: number): number => {
    if (!drag) return 0;
    if (at === drag.from) return drag.dy;
    if (drag.from < drag.to && at > drag.from && at <= drag.to) return -drag.step;
    if (drag.to < drag.from && at >= drag.to && at < drag.from) return drag.step;
    return 0;
  };
  /** where a title would land, were the one dragged dropped now */
  const landing = (at: number): number => {
    if (!drag) return at;
    if (at === drag.from) return drag.to;
    const by = shift(at);
    return by > 0 ? at + 1 : by < 0 ? at - 1 : at;
  };
  shifts.current = new Map(shown.map((id, at) => [id, shift(at)]));

  return (
    <div className="games-order" data-dragging={drag ? "true" : undefined} data-fixed={fixed || undefined}>
      <p className="games-order__end">
        <Icon name="arrow-up" size={14} />
        {t("gamification:games.order.older")}
      </p>
      <ol className="games-order__line">
        {shown.map((id, at) => {
          const choice = byId[id];
          const place = mine ? mine.indexOf(id) : -1;
          const right = answer && mine ? place === at : undefined;
          return (
            <li
              key={id}
              className="games-order__item"
              ref={(node) => {
                if (node) nodes.current.set(id, node);
                else nodes.current.delete(id);
              }}
              data-right={right === undefined ? undefined : String(right)}
              data-lifted={drag?.id === id || undefined}
              style={{ "--shift": `${shift(at)}px` } as CSSProperties}
              onPointerDown={(event) => grab(event, id, at)}
              onPointerMove={follow}
              onPointerUp={drop}
              onPointerCancel={drop}
            >
              <span className="games-order__rank" aria-hidden="true">
                {right === undefined ? landing(at) + 1 : <Icon name={right ? "check" : "close"} size={14} />}
              </span>
              <span className="games-order__card">
                {choice?.image ? (
                  <img src={metadataImage(choice.image, "w92") ?? ""} alt="" draggable={false} />
                ) : null}
                <span className="games-order__title">
                  <span>{choice?.label}</span>
                  {right === false && place >= 0 ? (
                    <small>{t("gamification:games.order.was", { place: place + 1 })}</small>
                  ) : null}
                </span>
                {values?.[id] != null ? <b className="games-order__year">{values[id]}</b> : null}
                {!fixed ? (
                  <span className="games-order__moves">
                    <button
                      type="button"
                      disabled={at === 0}
                      aria-label={t("gamification:games.order.up", { title: choice?.label ?? "" })}
                      onClick={() => move(at, at - 1)}
                    >
                      <Icon name="chevron-up" size={16} />
                    </button>
                    <button
                      type="button"
                      disabled={at === shown.length - 1}
                      aria-label={t("gamification:games.order.down", { title: choice?.label ?? "" })}
                      onClick={() => move(at, at + 1)}
                    >
                      <Icon name="chevron-down" size={16} />
                    </button>
                  </span>
                ) : null}
                {!fixed ? (
                  <span className="games-order__grip" aria-hidden="true">
                    <Icon name="grip" size={18} />
                  </span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="games-order__end">
        <Icon name="arrow-down" size={14} />
        {t("gamification:games.order.newer")}
      </p>
      <p className="games-sr" aria-live="polite">
        {said}
      </p>
      {!answer && onAnswer ? (
        <div className="games-actions">
          <p className="games-muted">{t("gamification:games.order.drag")}</p>
          <Button disabled={disabled} onClick={() => onAnswer(order)}>
            <Icon name="check" size={16} />
            {t("gamification:games.send")}
          </Button>
        </div>
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
  round = 1,
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
  /** the round's number: its image and its sound are asked for by it, never the browser's last ones */
  round?: number | undefined;
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
  const arranged = useRef<string[] | null>(null); // a timeline put in order, not sent yet
  useEffect(() => {
    if (left > 0 || answered || revealed || timedOut.current) return;
    if (arranged.current && onAnswer && !busy) {
      timedOut.current = true;
      onAnswer({ order: arranged.current });
    } else if (onTimeout) {
      timedOut.current = true;
      onTimeout();
    }
  }, [left, answered, revealed, onTimeout, onAnswer, busy]);
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
  // 1, 2, 3, 4 (or A, B, C, D) on a keyboard answer as a tap does
  useEffect(() => {
    if (disabled || question.ordered) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target;
      if (target instanceof Element && target.closest("input, textarea, select, [contenteditable]")) return;
      const key = event.key.toUpperCase();
      const at = /^[1-9]$/.test(key) ? Number(key) - 1 : LETTERS.indexOf(key);
      const choice = at >= 0 ? question.choices[at] : undefined;
      if (!choice) return;
      event.preventDefault();
      onAnswer?.({ choice: choice.id });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [disabled, question, onAnswer]);
  return (
    <section
      className="games-question"
      data-game={question.game}
      data-phase={phase}
      data-screen={screen || undefined}
      aria-live="polite"
    >
      <div className="games-stage">
        {!revealed ? <TimerBar left={left} seconds={seconds} /> : null}
        <Prompt
          question={question}
          base={base}
          round={round}
          elapsed={elapsed}
          seconds={seconds}
          revealed={revealed}
        />
      </div>
      {question.ordered ? (
        <Ordering
          key={`${base}:${question.choices.map((c) => c.id).join()}`}
          question={question}
          disabled={disabled}
          onAnswer={onAnswer ? (order) => onAnswer({ order }) : undefined}
          onArrange={(order, touched) => {
            arranged.current = touched ? order : null;
          }}
          answer={revealed && Array.isArray(answer) ? answer : undefined}
          given={Array.isArray(given) ? (given as string[]) : undefined}
          values={values}
        />
      ) : (
        <div className="games-choices" data-layout={posters ? "posters" : "list"}>
          {question.choices.map((choice, at) => {
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
                {choice.image ? (
                  <img src={metadataImage(choice.image, "w342") ?? ""} alt="" />
                ) : (
                  <span className="games-choice__key" aria-hidden="true">
                    {LETTERS[at]}
                  </span>
                )}
                <span className="games-choice__label">{choice.label}</span>
                {values?.[choice.id] ? <b className="games-choice__value">{values[choice.id]}</b> : null}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
