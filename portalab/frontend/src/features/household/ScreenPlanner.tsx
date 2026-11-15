import * as PopoverPrimitive from "@radix-ui/react-popover";
import {
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { Menu } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";
import { useMeasures } from "../media/insights/api";
import { type RestrictionSettings, SCREEN_MINUTES } from "./api";

/**
 * Issue 436: a profile's screen time as a week calendar — days side by side, hours down the side, like an
 * agenda. A tap (or a click) on a free hour puts a one-hour span there, a drag draws a longer one; a span is
 * dragged to move it (to another day too) and by its lower edge to lengthen it; a tap on a span opens its
 * card: its hours, its time (the whole span, or so many minutes in it), the other days it is on. Each day's
 * maximum sits in its header. A day without spans is open all day; a day with spans opens within them only.
 * Without ``onChange`` the calendar is only shown (a profile's own schedule).
 */
export type Span = { day: number; start: string; end: string; minutes?: number | null };
export type Plan = Pick<
  RestrictionSettings,
  "slots" | "week_minutes" | "daily_minutes" | "hours_from" | "hours_to"
>;

const DAYS = [0, 1, 2, 3, 4, 5, 6] as const;
const STEP = 15; // minutes a span snaps to
const TAP = 60; // the span a tap puts down
const DAY = 24 * 60;
const MOVE = 5; // pixels before a press becomes a drag
const BUDGETS = [15, 30, 45, 60, 90, 120, 180, 240] as const;

export const toMinutes = (hour: string): number => {
  const [h, m] = hour.split(":").map(Number) as [number, number];
  return h * 60 + m;
};
export const toHour = (minutes: number): string =>
  `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
/** « 16 », « 16:30 » — an hour as short as it gets, for narrow spans. */
const brief = (minutes: number) => (minutes % 60 ? toHour(minutes).replace(/^0/, "") : String(minutes / 60));
/** Monday first, as the plan counts its days. */
export const weekday = (date: Date) => (date.getDay() + 6) % 7;

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

/** What the calendar writes back: the spans, and the days' maximums (one value for all when they agree). */
export function planOf(spans: Span[], limits: (number | null)[]): Plan {
  const agree = limits.every((m) => m === limits[0]);
  const first = limits[0] ?? null;
  const daily = agree && (first === null || (SCREEN_MINUTES as readonly number[]).includes(first));
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
    (s) => !is(s, except) && s.day === candidate.day && candidate.start < s.end && s.start < candidate.end,
  );
const same = (a: Span, b: Span) => a.start === b.start && a.end === b.end;
/** The same span from one render to the next (each render copies them): a day holds one span a start. */
const is = (a: Span, b: Span | undefined) => b !== undefined && a.day === b.day && a.start === b.start;

/** The room around ``minute`` on a day, between its neighbouring spans. */
function room(spans: Span[], day: number, minute: number, except?: Span): [number, number] {
  let low = 0;
  let high = DAY;
  for (const s of spans) {
    if (is(s, except) || s.day !== day) continue;
    const [a, b] = [toMinutes(s.start), toMinutes(s.end)];
    if (b <= minute) low = Math.max(low, b);
    if (a >= minute) high = Math.min(high, a);
  }
  return [low, high];
}

type Drag =
  | {
      kind: "new";
      day: number;
      anchor: number;
      start: number;
      end: number;
      low: number;
      high: number;
      y: number;
    }
  | { kind: "move"; span: Span; day: number; start: number; end: number; grab: number }
  | { kind: "end"; span: Span; day: number; start: number; end: number; high: number };
type Press =
  | { span: Span; x: number; y: number; grab: number }
  | { day: number; minute: number; x: number; y: number };

export function ScreenPlanner({
  plan,
  onChange,
  label,
}: {
  plan: Plan;
  onChange?: ((plan: Plan) => void) | undefined;
  /** The calendar's name for assistive technologies (whose schedule it is). */
  label?: string | undefined;
}) {
  const t = useT();
  const measures = useMeasures();
  const id = useId();
  const spans = spansOf(plan);
  const limits = dayLimitsOf(plan);
  const editable = Boolean(onChange);
  const [selected, setSelected] = useState<{ day: number; start: string } | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [now, setNow] = useState(() => new Date());
  const press = useRef<Press | null>(null);
  const dragged = useRef(false);
  const tapped = useRef(false); // a finger's tap put a span down: its emulated mouse click is dropped
  const scroller = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const columns = useRef<Array<HTMLDivElement | null>>([]);
  const write = (next: Span[], nextLimits = limits) => onChange?.(planOf(next, nextLimits));
  const current = selected
    ? spans.find((s) => s.day === selected.day && s.start === selected.start)
    : undefined;
  const dayName = (day: number) => t(`household:editor.day.${day}`);
  const time = (minutes: number) => measures.duration(minutes * 60);
  const budget = (s: Span) => (s.minutes ? time(s.minutes) : t("household:planner.whole"));
  const top = (minute: number) => `${(minute / DAY) * 100}%`;
  const height = (a: number, b: number) => `${((b - a) / DAY) * 100}%`;
  const today = weekday(now);
  const clock = now.getHours() * 60 + now.getMinutes();

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);
  // opens on the morning (or the earliest span), the night a scroll away
  // biome-ignore lint/correctness/useExhaustiveDependencies: only when the calendar opens
  useLayoutEffect(() => {
    const box = scroller.current;
    if (!box) return;
    const first = Math.min(7 * 60, ...spans.map((s) => toMinutes(s.start)));
    box.scrollTop = (Math.max(0, first - 30) / DAY) * box.scrollHeight;
  }, []);

  const minuteAt = (clientY: number, snap: (value: number) => number = Math.round) => {
    const rect = body.current?.getBoundingClientRect();
    if (!rect || rect.height === 0) return 0;
    const raw = ((clientY - rect.top) / rect.height) * DAY;
    return Math.min(DAY, Math.max(0, snap(raw / STEP) * STEP));
  };
  const dayAt = (clientX: number, fallback: number) => {
    const rects = columns.current.map((c) => c?.getBoundingClientRect());
    const found = rects.findIndex((r) => r && r.width > 0 && clientX >= r.left && clientX < r.right);
    if (found >= 0) return found;
    const [first, last] = [rects[0], rects[6]];
    if (first && first.width > 0 && clientX < first.left) return 0;
    if (last && last.width > 0 && clientX >= last.right) return 6;
    return fallback;
  };

  /** A tap on a free hour: a one-hour span from the half hour, within the room there. */
  const putAt = (day: number, minute: number) => {
    const [low, high] = room(spans, day, minute);
    const length = Math.min(TAP, high - low);
    if (length < STEP) return;
    const start = Math.max(low, Math.min(Math.floor(minute / 30) * 30, high - length));
    write([...spans, { day, start: toHour(start), end: toHour(start + length), minutes: null }]);
    setSelected({ day, start: toHour(start) });
  };

  const down = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!editable || event.button !== 0) return;
    const target = event.target as HTMLElement;
    const column = target.closest<HTMLElement>("[data-day]");
    if (!column) return;
    const day = Number(column.dataset.day);
    const node = target.closest<HTMLElement>("[data-span]");
    const span = node ? spans.find((s) => s.day === day && s.start === node.dataset.span) : undefined;
    const minute = minuteAt(event.clientY);
    dragged.current = false;
    if (span && target.closest("[data-edge]")) {
      event.preventDefault();
      event.currentTarget.setPointerCapture?.(event.pointerId);
      const [, high] = room(spans, day, toMinutes(span.start), span);
      setDrag({ kind: "end", span, day, start: toMinutes(span.start), end: toMinutes(span.end), high });
      return;
    }
    if (span) {
      press.current = { span, x: event.clientX, y: event.clientY, grab: minute - toMinutes(span.start) };
      return;
    }
    if (current) return; // a press beside the open card only closes it
    const [low, high] = room(spans, day, minute);
    if (high - low < STEP) return;
    press.current = { day, minute, x: event.clientX, y: event.clientY };
    if (event.pointerType === "touch") return; // a finger scrolls the calendar; a tap puts a span down
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const start = Math.max(low, Math.min(minuteAt(event.clientY, Math.floor), high - STEP));
    setDrag({ kind: "new", day, anchor: start, start, end: start + STEP, low, high, y: event.clientY });
  };

  const move = (event: ReactPointerEvent<HTMLDivElement>) => {
    const pressed = press.current;
    let active = drag;
    if (!active) {
      const far = pressed && Math.hypot(event.clientX - pressed.x, event.clientY - pressed.y) > MOVE;
      if (!pressed || !("span" in pressed) || !far) return;
      // a span pressed and pulled: it follows the pointer from now on
      event.currentTarget.setPointerCapture?.(event.pointerId);
      dragged.current = true;
      const s = pressed.span;
      const [start, end] = [toMinutes(s.start), toMinutes(s.end)];
      active = { kind: "move", span: s, day: s.day, start, end, grab: pressed.grab };
    }
    const minute = minuteAt(event.clientY);
    if (active.kind === "new") {
      const [a, b] = minute >= active.anchor ? [active.anchor, minute] : [minute, active.anchor + STEP];
      setDrag({
        ...active,
        start: Math.max(active.low, Math.min(a, b - STEP)),
        end: Math.min(active.high, Math.max(b, a + STEP)),
      });
    } else if (active.kind === "end") {
      setDrag({ ...active, end: Math.min(active.high, Math.max(minute, active.start + STEP)) });
    } else {
      const length = active.end - active.start;
      const start = Math.min(DAY - length, Math.max(0, minute - Math.round(active.grab / STEP) * STEP));
      const day = dayAt(event.clientX, active.day);
      const moved = { day, start: toHour(start), end: toHour(start + length) };
      setDrag(overlaps(spans, moved, active.span) ? active : { ...active, day, start, end: start + length });
    }
  };

  const up = (event: ReactPointerEvent<HTMLDivElement>) => {
    const pressed = press.current;
    press.current = null;
    if (drag) {
      setDrag(null);
      if (drag.kind === "new") {
        if (Math.abs(event.clientY - drag.y) <= MOVE) putAt(drag.day, drag.anchor);
        else {
          const start = toHour(drag.start);
          write([...spans, { day: drag.day, start, end: toHour(drag.end), minutes: null }]);
          setSelected({ day: drag.day, start });
        }
        return;
      }
      const was = drag.span;
      const next = { ...was, day: drag.day, start: toHour(drag.start), end: toHour(drag.end) };
      write(spans.map((s) => (is(s, was) ? next : s)));
      setSelected(null);
      return;
    }
    const near = pressed && Math.hypot(event.clientX - pressed.x, event.clientY - pressed.y) <= MOVE;
    if (pressed && !("span" in pressed) && near) {
      tapped.current = event.pointerType === "touch";
      putAt(pressed.day, pressed.minute);
    }
  };

  /** « Add a span »: the first free two hours of the week from 16:00 (the keyboard's way in). */
  const add = () => {
    for (const day of DAYS) {
      for (const from of [16 * 60, 14 * 60, 10 * 60, 18 * 60, 8 * 60, 20 * 60, 0]) {
        for (const length of [120, 60, 30]) {
          const end = toHour(Math.min(DAY, from + length));
          const candidate = { day, start: toHour(from), end, minutes: null };
          if (!overlaps(spans, candidate)) {
            write([...spans, candidate]);
            setSelected({ day, start: candidate.start });
            return;
          }
        }
      }
    }
  };

  const copyMonday = (days: readonly number[]) => {
    const monday = spans.filter((s) => s.day === 0);
    const kept = spans.filter((s) => !days.includes(s.day) || s.day === 0);
    const copied = days.filter((d) => d !== 0).flatMap((day) => monday.map((s) => ({ ...s, day })));
    write(
      [...kept, ...copied],
      limits.map((m, day) => (days.includes(day) ? (limits[0] ?? null) : m)),
    );
  };

  /** The open span changed — and with it the same span on the other days it is on. */
  const edit = (changes: Partial<Span>) => {
    if (!current) return;
    const next = { ...current, ...changes };
    let list = spans.map((s) => (s === current ? next : s));
    for (const sibling of spans.filter((s) => s.day !== current.day && same(s, current))) {
      const moved = { ...sibling, start: next.start, end: next.end, minutes: next.minutes ?? null };
      if (!overlaps(list, moved, sibling)) list = list.map((s) => (s === sibling ? moved : s));
    }
    write(list);
    setSelected({ day: current.day, start: next.start });
  };
  const toggleDay = (day: number, on: boolean) => {
    if (!current) return;
    if (!on) {
      write(spans.filter((s) => !(s.day === day && same(s, current))));
      return;
    }
    const copy = { ...current, day };
    write([...spans.filter((s) => !(s.day === day && overlaps([s], copy))), copy]);
  };

  const setLimit = (day: number, value: number | null) =>
    write(
      spans,
      limits.map((m, d) => (d === day ? value : m)),
    );
  const limitText = (value: number | null) =>
    value === null
      ? t("household:planner.noMax")
      : value === 0
        ? t("household:planner.noScreen")
        : t("household:planner.dayMax", { time: time(value) });

  const placed = spans.map((s) =>
    drag && drag.kind !== "new" && is(s, drag.span)
      ? { span: s, day: drag.day, start: drag.start, end: drag.end, live: true }
      : { span: s, day: s.day, start: toMinutes(s.start), end: toMinutes(s.end), live: false },
  );

  return (
    <PopoverPrimitive.Root open={Boolean(current)} onOpenChange={(open) => (open ? null : setSelected(null))}>
      <section
        className="screen-cal"
        aria-label={label ?? t("household:planner.title")}
        data-editable={editable || undefined}
      >
        {editable ? (
          <div className="screen-cal__bar">
            <p className="household-editor__hint">{t("household:planner.hint")}</p>
            <div className="screen-cal__tools">
              <Button variant="secondary" type="button" onClick={add}>
                <Icon name="plus" size={14} />
                {t("household:planner.addSpan")}
              </Button>
              <Menu
                label={t("household:planner.copy")}
                trigger={
                  <Button variant="ghost" type="button">
                    <Icon name="copy" size={14} />
                    {t("household:planner.copy")}
                  </Button>
                }
                items={[
                  {
                    key: "weekdays",
                    label: t("household:planner.copyWeekdays"),
                    onSelect: () => copyMonday([1, 2, 3, 4]),
                  },
                  { key: "all", label: t("household:planner.copyAll"), onSelect: () => copyMonday(DAYS) },
                ]}
              />
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
          </div>
        ) : null}
        <div className="screen-cal__frame">
          <div className="screen-cal__head">
            <span className="screen-cal__corner" />
            {DAYS.map((day) => {
              const limit = limits[day] ?? null;
              const name = t("household:planner.maxOf", { day: dayName(day) });
              return (
                <div key={day} className="screen-cal__dayhead" data-today={day === today || undefined}>
                  <strong title={dayName(day)}>{t(`household:editor.dayShort.${day}`)}</strong>
                  {editable ? (
                    <Menu
                      label={name}
                      trigger={
                        <button
                          type="button"
                          className="screen-cal__max"
                          data-set={limit !== null || undefined}
                          aria-label={`${name} : ${limitText(limit)}`}
                        >
                          {limitText(limit)}
                        </button>
                      }
                      items={[
                        {
                          key: "none",
                          label: t("household:planner.noMaxLong"),
                          onSelect: () => setLimit(day, null),
                        },
                        {
                          key: "0",
                          label: t("household:planner.noScreen"),
                          onSelect: () => setLimit(day, 0),
                        },
                        ...SCREEN_MINUTES.map((minutes) => ({
                          key: String(minutes),
                          label: t("household:planner.dayMax", { time: time(minutes) }),
                          onSelect: () => setLimit(day, minutes),
                        })),
                      ]}
                    />
                  ) : (
                    <span className="screen-cal__max" data-set={limit !== null || undefined}>
                      {limitText(limit)}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          <div ref={scroller} className="screen-cal__scroll">
            <div className="screen-cal__grid">
              <div className="screen-cal__hours" aria-hidden="true">
                {Array.from({ length: 23 }, (_, i) => i + 1).map((hour) => (
                  <span key={hour} style={{ insetBlockStart: top(hour * 60) }}>
                    {toHour(hour * 60)}
                  </span>
                ))}
              </div>
              <div
                ref={body}
                className="screen-cal__body"
                onPointerDown={down}
                onPointerMove={move}
                onPointerUp={up}
                onTouchEnd={(event) => {
                  // the browser's click after a tap would land on the card just opened under the finger
                  if (tapped.current) event.preventDefault();
                  tapped.current = false;
                }}
                onPointerCancel={() => {
                  press.current = null;
                  setDrag(null);
                }}
              >
                {DAYS.map((day) => {
                  const ofDay = placed.filter((p) => p.day === day);
                  const closed = limits[day] === 0 || spans.some((s) => s.day === day);
                  return (
                    <div
                      key={day}
                      ref={(node) => {
                        columns.current[day] = node;
                      }}
                      className="screen-cal__day"
                      data-day={day}
                      data-closed={closed || undefined}
                      data-off={limits[day] === 0 || undefined}
                    >
                      {ofDay.map(({ span: s, start, end, live }) => {
                        const active = current === s;
                        const block = (
                          <div
                            key={s.start}
                            className="screen-cal__span"
                            data-span={s.start}
                            data-active={active || undefined}
                            data-live={live || undefined}
                            data-limited={s.minutes ? true : undefined}
                            data-short={end - start < 60 || undefined}
                            data-mid={end - start < 120 || undefined}
                            style={{ insetBlockStart: top(start), blockSize: height(start, end) }}
                          >
                            <button
                              type="button"
                              className="screen-cal__label"
                              tabIndex={editable ? 0 : -1}
                              aria-label={t("household:planner.slot", {
                                day: dayName(day),
                                start: toHour(start),
                                end: toHour(end),
                                time: budget(s),
                              })}
                              aria-haspopup={editable ? "dialog" : undefined}
                              aria-expanded={editable ? active : undefined}
                              aria-controls={active ? `${id}-card` : undefined}
                              onClick={() => {
                                if (!editable) return;
                                if (dragged.current) {
                                  dragged.current = false;
                                  return;
                                }
                                setSelected({ day, start: s.start }); // a touch's click after a tap must not close it
                              }}
                            >
                              <span className="screen-cal__when">
                                {brief(start)}–<wbr />
                                {brief(end)}
                              </span>
                              <span className="screen-cal__budget">
                                {s.minutes ? time(s.minutes) : t("household:planner.wholeShort")}
                              </span>
                            </button>
                            {editable ? (
                              <span className="screen-cal__edge" data-edge="end" aria-hidden="true" />
                            ) : null}
                          </div>
                        );
                        return active ? (
                          <PopoverPrimitive.Anchor asChild key={s.start}>
                            {block}
                          </PopoverPrimitive.Anchor>
                        ) : (
                          block
                        );
                      })}
                      {drag?.kind === "new" && drag.day === day ? (
                        <div
                          className="screen-cal__span screen-cal__span--draft"
                          style={{
                            insetBlockStart: top(drag.start),
                            blockSize: height(drag.start, drag.end),
                          }}
                        >
                          <span className="screen-cal__when">
                            {brief(drag.start)}–{brief(drag.end)}
                          </span>
                        </div>
                      ) : null}
                      {day === today ? (
                        <span
                          className="screen-cal__now"
                          style={{ insetBlockStart: top(clock) }}
                          aria-hidden="true"
                        />
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
        <ul className="screen-cal__legend">
          <li data-swatch="whole">{t("household:planner.legendWhole")}</li>
          <li data-swatch="limited">{t("household:planner.legendLimited")}</li>
          <li data-swatch="closed">{t("household:planner.legendClosed")}</li>
          <li data-swatch="open">{t("household:planner.legendOpen")}</li>
        </ul>
      </section>
      {current ? (
        <PopoverPrimitive.Portal>
          <PopoverPrimitive.Content
            id={`${id}-card`}
            className="ds-popover screen-cal__card"
            side={globalThis.matchMedia?.("(max-width: 40rem)").matches ? "bottom" : "right"}
            align="start"
            sideOffset={6}
            collisionPadding={12}
            aria-label={t("household:planner.edit", { day: dayName(current.day) })}
            onOpenAutoFocus={(event) => event.preventDefault()}
            // a tap's focus lands on the page after the card opens: only a press beside it (or Escape) closes it
            onFocusOutside={(event) => event.preventDefault()}
          >
            <SpanCard
              span={current}
              spans={spans}
              onEdit={edit}
              onDay={toggleDay}
              onDelete={() => {
                write(spans.filter((s) => s !== current));
                setSelected(null);
              }}
              onClose={() => setSelected(null)}
            />
          </PopoverPrimitive.Content>
        </PopoverPrimitive.Portal>
      ) : null}
    </PopoverPrimitive.Root>
  );
}

/** A span's card: its hours, its time, the other days it is on — every change applied at once. */
function SpanCard({
  span,
  spans,
  onEdit,
  onDay,
  onDelete,
  onClose,
}: {
  span: Span;
  spans: Span[];
  onEdit: (changes: Partial<Span>) => void;
  onDay: (day: number, on: boolean) => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const t = useT();
  const measures = useMeasures();
  const [start, end] = [toMinutes(span.start), toMinutes(span.end)];
  const [low, high] = room(spans, span.day, start, span);
  const steps = (from: number, to: number) =>
    Array.from({ length: Math.max(0, Math.floor((to - from) / STEP) + 1) }, (_, i) => from + i * STEP);
  const budgets = [
    ...new Set([...BUDGETS.filter((m) => m < end - start), ...(span.minutes ? [span.minutes] : [])]),
  ].sort((a, b) => a - b);
  return (
    <div className="screen-card">
      <div className="screen-card__head">
        <h4>{t(`household:editor.day.${span.day}`)}</h4>
        <button
          type="button"
          className="screen-card__close"
          aria-label={t("household:planner.close")}
          onClick={onClose}
        >
          <Icon name="close" size={16} />
        </button>
      </div>
      <div className="screen-card__hours">
        <label>
          <span>{t("household:editor.hoursFrom")}</span>
          <select value={start} onChange={(event) => onEdit({ start: toHour(Number(event.target.value)) })}>
            {steps(low, end - STEP).map((m) => (
              <option key={m} value={m}>
                {toHour(m)}
              </option>
            ))}
          </select>
        </label>
        <span aria-hidden="true">→</span>
        <label>
          <span>{t("household:editor.hoursTo")}</span>
          <select value={end} onChange={(event) => onEdit({ end: toHour(Number(event.target.value)) })}>
            {steps(start + STEP, high).map((m) => (
              <option key={m} value={m}>
                {toHour(m)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <fieldset className="screen-card__chips">
        <legend>{t("household:planner.budget")}</legend>
        <button
          type="button"
          aria-pressed={!span.minutes}
          data-active={!span.minutes || undefined}
          onClick={() => onEdit({ minutes: null })}
        >
          {t("household:planner.whole")}
        </button>
        {budgets.map((minutes) => (
          <button
            key={minutes}
            type="button"
            aria-pressed={span.minutes === minutes}
            data-active={span.minutes === minutes || undefined}
            onClick={() => onEdit({ minutes })}
          >
            {measures.duration(minutes * 60)}
          </button>
        ))}
      </fieldset>
      <fieldset className="screen-card__chips screen-card__days">
        <legend>{t("household:planner.alsoOn")}</legend>
        {DAYS.map((day) => {
          const on = day === span.day || spans.some((s) => s.day === day && same(s, span));
          return (
            <label key={day} data-checked={on || undefined}>
              <input
                type="checkbox"
                checked={on}
                disabled={day === span.day}
                onChange={(event) => onDay(day, event.target.checked)}
              />
              {t(`household:editor.dayShort.${day}`)}
            </label>
          );
        })}
      </fieldset>
      <div className="screen-card__actions">
        <Button variant="ghost" type="button" onClick={onDelete}>
          <Icon name="trash" size={14} />
          {t("household:planner.delete")}
        </Button>
        <Button type="button" onClick={onClose}>
          <Icon name="check" size={14} />
          {t("household:planner.done")}
        </Button>
      </div>
    </div>
  );
}
