import { Fragment, type ReactNode, useMemo } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import "./month-grid.css";

/**
 * Month grid shared by the calendar widget and the calendar page (027): each kind has its colour **and**
 * its icon (films, series, books, events, campaigns, maintenance, incidents, news); something lasting
 * several days is a bar across those days (cut at the week's edge, continued on the next row); one-day
 * items are dots (compact) or chips (full). Choosing a day hands it to ``onPick``.
 */
export interface CalEntry {
  title: string;
  kind: string;
  category?: string | null | undefined;
  status?: string | null | undefined;
  time?: string | null | undefined;
  route: string;
  /** First and last day, ``YYYY-MM-DD`` (inclusive). */
  date: string;
  end: string;
}

export const CATEGORY_ICONS: Record<string, string> = {
  movie: "film",
  series: "tv",
  book: "book",
  event: "users",
  campaign: "star",
  maintenance: "wrench",
  incident: "alert",
  news: "newspaper",
  other: "calendar",
};

export function categoryOf(entry: Pick<CalEntry, "kind" | "category">): string {
  switch (entry.kind) {
    case "media_release":
      return entry.category && entry.category in CATEGORY_ICONS ? entry.category : "movie";
    case "community_event":
    case "event":
      return "event";
    case "campaign":
    case "maintenance":
    case "incident":
    case "news":
      return entry.kind;
    default:
      return "other";
  }
}

function addDays(day: string, n: number): string {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** The days shown for a month: whole weeks from the week of the 1st (``firstDay`` 0 = Monday). */
export function monthDays(month: string, firstDay = 0): string[] {
  const first = `${month.slice(0, 7)}-01`;
  const weekday = (new Date(`${first}T12:00:00Z`).getUTCDay() + 6) % 7; // 0 = Monday
  const start = addDays(first, -((weekday - firstDay + 7) % 7));
  const next = new Date(`${first}T12:00:00Z`);
  next.setUTCMonth(next.getUTCMonth() + 1);
  const last = addDays(next.toISOString().slice(0, 10), -1);
  const days: string[] = [];
  for (let day = start; day <= last || days.length % 7 !== 0; day = addDays(day, 1)) days.push(day);
  return days;
}

interface Bar {
  entry: CalEntry;
  from: number;
  to: number;
  lane: number;
  continuesBefore: boolean;
  continuesAfter: boolean;
}

/** Bars of the multi-day entries in one week, each on the first free lane. */
function lay(week: string[], entries: CalEntry[]): Bar[] {
  const first = week[0] as string;
  const last = week[week.length - 1] as string;
  const lanes: number[][] = [];
  const bars: Bar[] = [];
  const spanning = entries
    .filter((e) => e.end > e.date && e.date <= last && e.end >= first)
    .sort((a, b) => a.date.localeCompare(b.date) || b.end.localeCompare(a.end));
  for (const entry of spanning) {
    const from = Math.max(0, week.indexOf(entry.date < first ? first : entry.date));
    const to = week.indexOf(entry.end > last ? last : entry.end);
    let lane = lanes.findIndex((used) => used.every((col) => col < from || col > to));
    if (lane < 0) {
      lanes.push([]);
      lane = lanes.length - 1;
    }
    for (let col = from; col <= to; col += 1) lanes[lane]?.push(col);
    bars.push({
      entry,
      from,
      to,
      lane,
      continuesBefore: entry.date < first,
      continuesAfter: entry.end > last,
    });
  }
  return bars;
}

export function MonthGrid({
  days,
  month,
  today,
  entries,
  compact = false,
  maxLanes = compact ? 2 : 3,
  picked,
  onPick,
  weekdayLabels,
}: {
  days: string[];
  month?: string | undefined;
  today: string;
  entries: CalEntry[];
  compact?: boolean;
  maxLanes?: number;
  picked?: string | null;
  onPick?: (day: string | null) => void;
  weekdayLabels?: string[];
}) {
  const t = useT();
  const weeks = useMemo(
    () => Array.from({ length: Math.ceil(days.length / 7) }, (_, i) => days.slice(i * 7, i * 7 + 7)),
    [days],
  );
  const singles = useMemo(() => {
    const map = new Map<string, CalEntry[]>();
    for (const entry of entries) {
      if (entry.end > entry.date) continue;
      map.set(entry.date, [...(map.get(entry.date) ?? []), entry]);
    }
    return map;
  }, [entries]);
  const countOn = (day: string) => entries.filter((e) => e.date <= day && e.end >= day).length;
  const labels =
    weekdayLabels ??
    (days.slice(0, 7).map((day) =>
      new Date(`${day}T12:00:00Z`).toLocaleDateString(undefined, {
        weekday: compact ? "narrow" : "short",
        timeZone: "UTC",
      }),
    ) as string[]);
  return (
    <div className="month-grid" data-compact={compact || undefined}>
      <div className="month-grid__weekdays" aria-hidden="true">
        {labels.map((label, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the seven weekdays are positional
          <span key={i}>{label}</span>
        ))}
      </div>
      {weeks.map((week) => {
        const bars = lay(week, entries);
        const shownBars = bars.filter((bar) => bar.lane < maxLanes);
        const lanes = Math.min(maxLanes, Math.max(0, ...bars.map((bar) => bar.lane + 1)));
        const hidden = (col: number) =>
          bars.filter((b) => b.lane >= maxLanes && b.from <= col && b.to >= col).length;
        return (
          <div key={week[0]} className="month-grid__week" style={{ "--lanes": lanes } as React.CSSProperties}>
            {week.map((day, col) => {
              const count = countOn(day);
              const date = new Date(`${day}T12:00:00Z`);
              return (
                <button
                  key={day}
                  type="button"
                  className="month-grid__day"
                  style={{ gridColumn: col + 1 }}
                  data-today={day === today || undefined}
                  data-outside={month && day.slice(0, 7) !== month.slice(0, 7) ? true : undefined}
                  data-busy={count ? true : undefined}
                  aria-pressed={picked === day}
                  aria-label={`${date.toLocaleDateString(undefined, { day: "numeric", month: "long", timeZone: "UTC" })}${
                    count ? ` · ${t("calendar:count", { count })}` : ""
                  }`}
                  onClick={() => onPick?.(picked === day ? null : day)}
                >
                  <span className="month-grid__num">{date.getUTCDate()}</span>
                </button>
              );
            })}
            {shownBars.map((bar) => {
              const category = categoryOf(bar.entry);
              const body: ReactNode = (
                <>
                  <Icon name={CATEGORY_ICONS[category] ?? "calendar"} size={compact ? 10 : 12} />
                  {compact ? null : <span>{bar.entry.title}</span>}
                </>
              );
              const style = {
                gridColumn: `${bar.from + 1} / ${bar.to + 2}`,
                gridRow: bar.lane + 2,
              } as React.CSSProperties;
              const props = {
                className: "month-grid__bar",
                style,
                "data-category": category,
                "data-status": bar.entry.status ?? undefined,
                "data-before": bar.continuesBefore || undefined,
                "data-after": bar.continuesAfter || undefined,
                title: bar.entry.title,
              };
              return compact ? (
                <span
                  key={`${bar.entry.kind}-${bar.entry.title}-${bar.entry.date}`}
                  {...props}
                  aria-hidden="true"
                >
                  {body}
                </span>
              ) : (
                <Link
                  key={`${bar.entry.kind}-${bar.entry.title}-${bar.entry.date}`}
                  to={bar.entry.route}
                  {...props}
                >
                  {body}
                </Link>
              );
            })}
            {week.map((day, col) => {
              const list = singles.get(day) ?? [];
              const more = hidden(col);
              if (!list.length && !more) return <Fragment key={`s-${day}`} />;
              const limit = compact ? 4 : 3;
              return (
                <span
                  key={`s-${day}`}
                  className="month-grid__singles"
                  style={{ gridColumn: col + 1, gridRow: lanes + 2 }}
                >
                  {list.slice(0, limit).map((entry) => {
                    const category = categoryOf(entry);
                    return compact ? (
                      <span
                        key={`${entry.kind}-${entry.title}`}
                        className="month-grid__dot"
                        data-category={category}
                        aria-hidden="true"
                      />
                    ) : (
                      <Link
                        key={`${entry.kind}-${entry.title}`}
                        to={entry.route}
                        className="month-grid__chip"
                        data-category={category}
                        data-status={entry.status ?? undefined}
                        title={entry.title}
                      >
                        <Icon name={CATEGORY_ICONS[category] ?? "calendar"} size={11} />
                        <span>{entry.title}</span>
                      </Link>
                    );
                  })}
                  {list.length - limit + more > 0 ? (
                    <span className="month-grid__more">+{Math.max(0, list.length - limit) + more}</span>
                  ) : null}
                </span>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

/** The kinds present, each with its colour and icon (never colour alone). */
export function CalendarLegend({ entries }: { entries: CalEntry[] }) {
  const t = useT();
  const present = [...new Set(entries.map(categoryOf))];
  if (!present.length) return null;
  return (
    <ul className="month-grid__legend" aria-label={t("calendar:legend")}>
      {present.map((category) => (
        <li key={category} data-category={category}>
          <Icon name={CATEGORY_ICONS[category] ?? "calendar"} size={12} />
          {t(`calendar:category.${category}`)}
        </li>
      ))}
    </ul>
  );
}
