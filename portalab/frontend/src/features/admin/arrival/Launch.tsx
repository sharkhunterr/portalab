import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import "./arrival.css";

/**
 * Issue 249 — the arrival wizard's waiting screens: while the portal is being put in place (the account, the
 * identity, each module; an archive brought in; the last checks before opening it), a ring tells how far it
 * is, the tasks below it which one runs, and slides go by (what the portal now offers, what comes next).
 * Every figure is the real progress; a task is shown at least a moment so the slides can be read.
 */
export type TaskState = "waiting" | "running" | "done" | "failed";

export interface LaunchTask {
  key: string;
  label: string;
  detail?: string | null;
  state: TaskState;
}

export interface Slide {
  icon: string;
  title: string;
  text: string;
}

const PACE = import.meta.env.MODE === "test" ? 0 : 650; // the least a task is shown (ms)
const SLIDE_EVERY = 4500;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Tasks run one after the other, each one's state and the share of the running one kept for the ring; a task
 * that lasts longer than the others counts more (``weights``, 1 by default). */
export function useTasks(keys: readonly string[], weights: Readonly<Record<string, number>> = {}) {
  const initial = () => Object.fromEntries(keys.map((k) => [k, "waiting" as TaskState]));
  const [states, setStates] = useState<Record<string, TaskState>>(initial);
  const [share, setShare] = useState(0);
  const [detail, setDetail] = useState<string | null>(null);
  const run = useCallback(
    async <T,>(
      key: string,
      work: (progress: (share: number, detail?: string | null) => void) => Promise<T>,
    ): Promise<T> => {
      setStates((s) => ({ ...s, [key]: "running" }));
      setShare(0);
      setDetail(null);
      const started = Date.now();
      try {
        const result = await work((value, text) => {
          setShare(Math.max(0, Math.min(1, value)));
          if (text !== undefined) setDetail(text);
        });
        const left = PACE - (Date.now() - started);
        if (left > 0) await wait(left);
        setStates((s) => ({ ...s, [key]: "done" }));
        return result;
      } catch (error) {
        setStates((s) => ({ ...s, [key]: "failed" }));
        throw error;
      }
    },
    [],
  );
  const weight = (k: string) => weights[k] ?? 1;
  const total = keys.reduce((sum, k) => sum + weight(k), 0);
  const done = keys.filter((k) => states[k] === "done").reduce((sum, k) => sum + weight(k), 0);
  const running = keys.find((k) => states[k] === "running");
  const percent = total ? Math.round(((done + (running ? weight(running) * share : 0)) / total) * 100) : 0;
  return { states, percent, detail, run, finished: keys.every((k) => states[k] === "done") };
}

function Ring({ percent, done, failed }: { percent: number; done: boolean; failed: boolean }) {
  const radius = 54;
  const length = 2 * Math.PI * radius;
  return (
    <div className="launch__ring" data-done={done || undefined} data-failed={failed || undefined}>
      <svg viewBox="0 0 128 128" aria-hidden="true">
        <defs>
          <linearGradient id="launch-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--color-accent)" />
            <stop offset="100%" stopColor="var(--launch-accent-2)" />
          </linearGradient>
        </defs>
        <circle className="launch__track" cx="64" cy="64" r={radius} />
        <circle
          className="launch__arc"
          cx="64"
          cy="64"
          r={radius}
          strokeDasharray={length}
          strokeDashoffset={length * (1 - percent / 100)}
        />
      </svg>
      <span className="launch__value">
        {failed ? (
          <Icon name="alert" size={34} />
        ) : done ? (
          <Icon name="check" size={40} />
        ) : (
          <>
            {percent}
            <small>%</small>
          </>
        )}
      </span>
    </div>
  );
}

function Slides({ slides }: { slides: readonly Slide[] }) {
  const t = useT();
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (slides.length < 2) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % slides.length), SLIDE_EVERY);
    return () => clearInterval(timer);
  }, [slides.length]);
  const slide = slides[index % Math.max(1, slides.length)];
  if (!slide) return null;
  return (
    <div className="launch__slides">
      <article key={index} className="launch__slide">
        <span className="launch__slide-icon" aria-hidden="true">
          <Icon name={slide.icon} size={26} />
        </span>
        <div>
          <h3>{slide.title}</h3>
          <p>{slide.text}</p>
        </div>
      </article>
      {slides.length > 1 ? (
        <div className="launch__dots">
          {slides.map((s, i) => (
            <button
              key={s.title}
              type="button"
              aria-label={t("account:arrival.launch.slide", { n: i + 1, total: slides.length })}
              aria-current={i === index % slides.length || undefined}
              onClick={() => setIndex(i)}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function Launch({
  title,
  lead,
  tasks,
  percent,
  slides,
  failed = false,
  done = false,
  children,
}: {
  title: string;
  lead?: string | undefined;
  tasks: readonly LaunchTask[];
  percent: number;
  slides: readonly Slide[];
  failed?: boolean;
  done?: boolean;
  children?: ReactNode; // what to do once over (or failed)
}) {
  const t = useT();
  const current = tasks.find((task) => task.state === "running");
  return (
    <div className="launch" data-done={done || undefined}>
      <div className="launch__head">
        <div
          role="progressbar"
          aria-label={title}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={done ? 100 : percent}
        >
          <Ring percent={done ? 100 : percent} done={done} failed={failed} />
        </div>
        <div className="launch__title">
          <h2>{title}</h2>
          {lead ? <p>{lead}</p> : null}
          <p className="launch__now" aria-live="polite">
            {failed
              ? t("account:arrival.launch.failed")
              : done
                ? t("account:arrival.launch.done")
                : current
                  ? `${current.label}${current.detail ? ` · ${current.detail}` : ""}…`
                  : t("account:arrival.launch.starting")}
          </p>
        </div>
      </div>
      <ol className="launch__tasks">
        {tasks.map((task) => (
          <li key={task.key} data-state={task.state}>
            <span className="launch__mark" aria-hidden="true">
              {task.state === "done" ? (
                <Icon name="check" size={14} />
              ) : task.state === "failed" ? (
                <Icon name="close" size={14} />
              ) : task.state === "running" ? (
                <span className="launch__spinner" />
              ) : null}
            </span>
            <span>{task.label}</span>
            <span className="visually-hidden">{t(`account:arrival.launch.state.${task.state}`)}</span>
          </li>
        ))}
      </ol>
      {children}
      {!done && !failed ? <Slides slides={slides} /> : null}
    </div>
  );
}
