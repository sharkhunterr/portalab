import { type PointerEvent as ReactPointerEvent, useId, useRef, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { type RestrictionSettings, SCREEN_MINUTES } from "./api";

/**
 * Issue 432: a profile's screen time as a week planner — on each day's line, spans drawn with the pointer
 * (or « + »), each with its own time or open for its whole length, and a maximum for the day. A day without
 * spans is open all day; a day with spans opens within them only.
 */
export type Span = { day: number; start: string; end: string; minutes?: number | null };
type Plan = Pick<RestrictionSettings, "slots" | "week_minutes" | "daily_minutes" | "hours_from" | "hours_to">;

const DAYS = [0, 1, 2, 3, 4, 5, 6] as const;
const STEP = 30; // minutes a drawn span snaps to
const DAY = 24 * 60;
const MORNING = 6 * 60; // the line starts at 6:00 unless the night is shown

export const toMinutes = (hour: string): number => {
  const [h, m] = hour.split(":").map(Number) as [number, number];
  return h * 60 + m;
};
export const toHour = (minutes: number): string =>
  `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;

/** The plan's spans — the old allowed hours turned into spans on every day (split at midnight). */
export function spansOf(plan: Plan): Span[] {
  if (plan.slots?.length) return plan.slots.map((s) => ({ ...s }));
  if (!plan.hours_from || !plan.hours_to) return [];
  const [from, to] = [plan.hours_from, plan.hours_to];
  return DAYS.flatMap((day) =>
    from < to
      ? [{ day, start: from, end: to, minutes: null }]
      : [
          ...(to > "00:00" ? [{ day, start: "00:00", end: to, minutes: null }] : []),
          { day, start: from, end: "24:00", minutes: null },
        ],
  );
}

/** Each day's maximum (``null``: no limit, 0: no screen). */
export function dayLimitsOf(plan: Plan): (number | null)[] {
  return plan.week_minutes?.length === 7
    ? [...plan.week_minutes]
    : DAYS.map(() => plan.daily_minutes ?? null);
}

/** What the planner writes back: the spans, and the days' maximums (one value for all when they agree). */
export function planOf(spans: Span[], limits: (number | null)[]): Plan {
  const same = limits.every((m) => m === limits[0]);
  const first = limits[0] ?? null;
  const daily = same && (first === null || (SCREEN_MINUTES as readonly number[]).includes(first));
  return {
    slots: [...spans].sort((a, b) => a.day - b.day || a.start.localeCompare(b.start)),
    daily_minutes: daily ? first : null,
    week_minutes: daily ? null : limits,
    hours_from: null,
    hours_to: null,
  };
}

const overlaps = (spans: Span[], candidate: Span, except?: Span) =>
  spans.some(
    (s) => s !== except && s.day === candidate.day && candidate.start < s.end && s.start < candidate.end,
  );

/** The room around ``minute`` on a day, between its neighbouring spans. */
function room(spans: Span[], day: number, minute: number, except?: Span): [number, number] {
  let low = 0;
  let high = DAY;
  for (const s of spans) {
    if (s === except || s.day !== day) continue;
    const [a, b] = [toMinutes(s.start), toMinutes(s.end)];
    if (b <= minute) low = Math.max(low, b);
    if (a >= minute) high = Math.min(high, a);
  }
  return [low, high];
}

type Drag =
  | { kind: "new"; day: number; anchor: number; start: number; end: number; low: number; high: number }
  | { kind: "start" | "end"; span: Span; start: number; end: number; low: number; high: number };

export function ScreenPlanner({ plan, onChange }: { plan: Plan; onChange: (plan: Plan) => void }) {
  const t = useT();
  const id = useId();
  const spans = spansOf(plan);
  const limits = dayLimitsOf(plan);
  const [selected, setSelected] = useState<{ day: number; start: string } | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [night, setNight] = useState(false);
  const from = night || spans.some((s) => toMinutes(s.start) < MORNING) ? 0 : MORNING;
  const length = DAY - from;
  const at = (minute: number) => `${((minute - from) / length) * 100}%`;
  const width = (a: number, b: number) => `${((b - a) / length) * 100}%`;
  const ticks = Array.from({ length: length / 180 + 1 }, (_, i) => from / 60 + i * 3);
  const tracks = useRef<Array<HTMLDivElement | null>>([]);
  const write = (next: Span[], nextLimits = limits) => onChange(planOf(next, nextLimits));
  const current = selected
    ? spans.find((s) => s.day === selected.day && s.start === selected.start)
    : undefined;
  const dayName = (day: number) => t(`household:editor.day.${day}`);
  const span = (s: Span) =>
    s.minutes ? t("household:editor.screenMinutes", { minutes: s.minutes }) : t("household:planner.whole");

  const minuteAt = (day: number, clientX: number) => {
    const rect = tracks.current[day]?.getBoundingClientRect();
    if (!rect || rect.width === 0) return 0;
    const raw = from + ((clientX - rect.left) / rect.width) * length;
    return Math.min(DAY, Math.max(from, Math.round(raw / STEP) * STEP));
  };

  const startNew = (day: number, event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || event.target !== event.currentTarget) return;
    const minute = Math.min(DAY - STEP, minuteAt(day, event.clientX));
    const [low, high] = room(spans, day, minute);
    if (high - low < STEP) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const start = Math.max(low, Math.min(minute, high - STEP));
    setDrag({ kind: "new", day, anchor: start, start, end: start + STEP, low, high });
  };
  const startResize = (s: Span, edge: "start" | "end", event: ReactPointerEvent<HTMLElement>) => {
    event.stopPropagation();
    event.preventDefault();
    tracks.current[s.day]?.setPointerCapture?.(event.pointerId);
    const [low, high] = room(spans, s.day, toMinutes(s.start), s);
    setDrag({ kind: edge, span: s, start: toMinutes(s.start), end: toMinutes(s.end), low, high });
  };
  const move = (day: number, event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag) return;
    const minute = minuteAt(day, event.clientX);
    if (drag.kind === "new") {
      const [a, b] = minute >= drag.anchor ? [drag.anchor, minute] : [minute, drag.anchor + STEP];
      setDrag({
        ...drag,
        start: Math.max(drag.low, Math.min(a, b - STEP)),
        end: Math.min(drag.high, Math.max(b, a + STEP)),
      });
    } else if (drag.kind === "start") {
      setDrag({ ...drag, start: Math.max(drag.low, Math.min(minute, drag.end - STEP)) });
    } else {
      setDrag({ ...drag, end: Math.min(drag.high, Math.max(minute, drag.start + STEP)) });
    }
  };
  const finish = () => {
    if (!drag) return;
    const [start, end] = [toHour(drag.start), toHour(drag.end)];
    if (drag.kind === "new") {
      write([...spans, { day: drag.day, start, end, minutes: null }]);
      setSelected({ day: drag.day, start });
    } else {
      const was = drag.span;
      write(spans.map((s) => (s === was ? { ...s, start, end } : s)));
      setSelected({ day: was.day, start });
    }
    setDrag(null);
  };

  /** « + »: a span in the day's first free two hours from 16:00 (or anywhere). */
  const add = (day: number) => {
    const wanted = [16 * 60, 14 * 60, 10 * 60, 18 * 60, 8 * 60, 20 * 60, 0];
    for (const from of wanted) {
      for (const length of [120, 60, 30]) {
        const candidate = {
          day,
          start: toHour(from),
          end: toHour(Math.min(DAY, from + length)),
          minutes: null,
        };
        if (!overlaps(spans, candidate)) {
          write([...spans, candidate]);
          setSelected({ day, start: candidate.start });
          return;
        }
      }
    }
  };

  const copyMonday = (days: readonly number[]) => {
    const monday = spans.filter((s) => s.day === 0);
    const kept = spans.filter((s) => !days.includes(s.day) || s.day === 0);
    const copied = days.filter((d) => d !== 0).flatMap((day) => monday.map((s) => ({ ...s, day })));
    const nextLimits = limits.map((m, day) => (days.includes(day) ? (limits[0] ?? null) : m));
    write([...kept, ...copied], nextLimits);
  };

  const shown = (s: Span) =>
    drag && drag.kind !== "new" && drag.span === s ? { start: drag.start, end: drag.end } : null;

  return (
    <div className="screen-planner">
      <p className="household-editor__hint">{t("household:planner.hint")}</p>
      <div className="screen-planner__grid">
        <div className="screen-planner__head" aria-hidden="true">
          <span />
          <div className="screen-planner__ticks">
            {ticks.map((hour) => (
              <span key={hour} style={{ insetInlineStart: at(hour * 60) }}>
                {hour}h
              </span>
            ))}
          </div>
          <span className="screen-planner__max">{t("household:planner.max")}</span>
        </div>
        {DAYS.map((day) => {
          const ofDay = spans.filter((s) => s.day === day);
          return (
            <div key={day} className="screen-planner__row" data-closed={limits[day] === 0 || undefined}>
              <span className="screen-planner__day">
                <strong>{t(`household:editor.dayShort.${day}`)}</strong>
                <button
                  type="button"
                  className="screen-planner__add"
                  aria-label={t("household:planner.add", { day: dayName(day) })}
                  title={t("household:planner.add", { day: dayName(day) })}
                  onClick={() => add(day)}
                >
                  <Icon name="plus" size={14} />
                </button>
              </span>
              <div
                ref={(node) => {
                  tracks.current[day] = node;
                }}
                className="screen-planner__track"
                style={{ "--segments": length / 180 } as React.CSSProperties}
                data-open-all-day={ofDay.length === 0 || undefined}
                onPointerDown={(event) => startNew(day, event)}
                onPointerMove={(event) => move(day, event)}
                onPointerUp={finish}
                onPointerCancel={() => setDrag(null)}
              >
                {ofDay.map((s) => {
                  const live = shown(s);
                  const [a, b] = live ? [live.start, live.end] : [toMinutes(s.start), toMinutes(s.end)];
                  const active = current === s;
                  return (
                    <div
                      key={s.start}
                      className="screen-planner__span"
                      data-active={active || undefined}
                      data-limited={s.minutes ? true : undefined}
                      data-narrow={b - a < 180 || undefined}
                      title={`${toHour(a)}–${toHour(b)} · ${span(s)}`}
                      style={{ insetInlineStart: at(a), inlineSize: width(a, b) }}
                    >
                      <span
                        className="screen-planner__edge"
                        data-edge="start"
                        onPointerDown={(event) => startResize(s, "start", event)}
                      />
                      <button
                        type="button"
                        className="screen-planner__label"
                        aria-label={t("household:planner.slot", {
                          day: dayName(day),
                          start: toHour(a),
                          end: toHour(b),
                          time: span(s),
                        })}
                        aria-expanded={active}
                        aria-controls={`${id}-editor`}
                        onClick={() => setSelected(active ? null : { day, start: s.start })}
                      >
                        <span className="screen-planner__hours">
                          {toHour(a)}–{toHour(b)}
                        </span>
                        <span className="screen-planner__time">{s.minutes ? `${s.minutes}′` : "∞"}</span>
                      </button>
                      <span
                        className="screen-planner__edge"
                        data-edge="end"
                        onPointerDown={(event) => startResize(s, "end", event)}
                      />
                    </div>
                  );
                })}
                {drag?.kind === "new" && drag.day === day ? (
                  <div
                    className="screen-planner__span screen-planner__span--draft"
                    style={{
                      insetInlineStart: at(drag.start),
                      inlineSize: width(drag.start, drag.end),
                    }}
                  >
                    <span className="screen-planner__hours">
                      {toHour(drag.start)}–{toHour(drag.end)}
                    </span>
                  </div>
                ) : null}
              </div>
              <label className="screen-planner__limit">
                <span className="visually-hidden">{t("household:planner.maxOf", { day: dayName(day) })}</span>
                <select
                  value={limits[day] ?? ""}
                  onChange={(event) =>
                    write(
                      spans,
                      limits.map((m, d) =>
                        d === day ? (event.target.value === "" ? null : Number(event.target.value)) : m,
                      ),
                    )
                  }
                >
                  <option value="">{t("household:editor.screenNone")}</option>
                  <option value={0}>{t("household:planner.noScreen")}</option>
                  {SCREEN_MINUTES.map((minutes) => (
                    <option key={minutes} value={minutes}>
                      {t("household:editor.screenMinutes", { minutes })}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          );
        })}
      </div>
      <div className="screen-planner__tools">
        {from > 0 || night ? (
          <Button variant="ghost" type="button" aria-pressed={night} onClick={() => setNight(!night)}>
            <Icon name="clock" size={14} />
            {t(night ? "household:planner.hideNight" : "household:planner.showNight")}
          </Button>
        ) : null}
        <Button variant="ghost" type="button" onClick={() => copyMonday([1, 2, 3, 4])}>
          <Icon name="copy" size={14} />
          {t("household:planner.copyWeekdays")}
        </Button>
        <Button variant="ghost" type="button" onClick={() => copyMonday(DAYS)}>
          <Icon name="copy" size={14} />
          {t("household:planner.copyAll")}
        </Button>
        {spans.length ? (
          <Button
            variant="ghost"
            type="button"
            onClick={() => {
              setSelected(null);
              write([]);
            }}
          >
            <Icon name="trash" size={14} />
            {t("household:planner.clear")}
          </Button>
        ) : null}
      </div>
      {current ? (
        <SpanEditor
          key={`${current.day}-${current.start}`}
          id={`${id}-editor`}
          span={current}
          spans={spans}
          onChange={(next, alsoOn) => {
            const others = spans.filter((s) => s !== current);
            const copies = alsoOn.map((day) => ({ ...next, day }));
            const kept = others.filter((s) => !copies.some((c) => overlaps([s], c)));
            write([...kept, next, ...copies]);
            setSelected({ day: next.day, start: next.start });
          }}
          onDelete={() => {
            write(spans.filter((s) => s !== current));
            setSelected(null);
          }}
          onClose={() => setSelected(null)}
        />
      ) : null}
    </div>
  );
}

/** One span: its hours, its time (the whole span, or so many minutes in it), copied to other days. */
function SpanEditor({
  id,
  span,
  spans,
  onChange,
  onDelete,
  onClose,
}: {
  id: string;
  span: Span;
  spans: Span[];
  onChange: (span: Span, alsoOn: number[]) => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const t = useT();
  const [start, setStart] = useState(span.start);
  const [end, setEnd] = useState(span.end === "24:00" ? "23:59" : span.end);
  const [minutes, setMinutes] = useState<number | null>(span.minutes ?? null);
  const [alsoOn, setAlsoOn] = useState<number[]>([]);
  const endHour = end === "23:59" ? "24:00" : end;
  const next: Span = { day: span.day, start, end: endHour, minutes };
  const wrong = !start || !end || endHour <= start;
  const clash = !wrong && overlaps(spans, next, span);
  return (
    <section
      id={id}
      className="screen-planner__editor"
      aria-label={t("household:planner.edit", { day: t(`household:editor.day.${span.day}`) })}
    >
      <h4>{t("household:planner.edit", { day: t(`household:editor.day.${span.day}`) })}</h4>
      <div className="screen-planner__fields">
        <TextField
          label={t("household:editor.hoursFrom")}
          type="time"
          step={STEP * 60}
          value={start}
          onChange={(event) => setStart(event.target.value)}
        />
        <TextField
          label={t("household:editor.hoursTo")}
          type="time"
          step={STEP * 60}
          value={end}
          onChange={(event) => setEnd(event.target.value)}
        />
        <SelectField
          label={t("household:planner.budget")}
          value={minutes ?? ""}
          onChange={(event) => setMinutes(event.target.value === "" ? null : Number(event.target.value))}
        >
          <option value="">{t("household:planner.whole")}</option>
          {SCREEN_MINUTES.map((m) => (
            <option key={m} value={m}>
              {t("household:editor.screenMinutes", { minutes: m })}
            </option>
          ))}
        </SelectField>
      </div>
      <fieldset className="screen-planner__also">
        <legend>{t("household:planner.alsoOn")}</legend>
        {DAYS.filter((day) => day !== span.day).map((day) => (
          <label key={day} data-checked={alsoOn.includes(day) || undefined}>
            <input
              type="checkbox"
              checked={alsoOn.includes(day)}
              onChange={(event) =>
                setAlsoOn((list) => (event.target.checked ? [...list, day] : list.filter((d) => d !== day)))
              }
            />
            {t(`household:editor.dayShort.${day}`)}
          </label>
        ))}
      </fieldset>
      {wrong || clash ? (
        <p role="alert" className="household-error">
          {t(wrong ? "household:planner.wrong" : "household:planner.overlap")}
        </p>
      ) : null}
      <div className="screen-planner__actions">
        <Button variant="ghost" type="button" onClick={onDelete}>
          <Icon name="trash" size={14} />
          {t("household:planner.delete")}
        </Button>
        <Button variant="ghost" type="button" onClick={onClose}>
          {t("household:editor.cancel")}
        </Button>
        <Button type="button" disabled={wrong || clash} onClick={() => onChange(next, alsoOn)}>
          <Icon name="check" size={14} />
          {t("household:planner.apply")}
        </Button>
      </div>
    </section>
  );
}
