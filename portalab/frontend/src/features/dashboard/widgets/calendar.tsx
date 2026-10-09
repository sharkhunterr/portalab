import { useMemo, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import {
  CATEGORY_ICONS,
  type CalEntry,
  CalendarLegend,
  categoryOf,
  MonthGrid,
  monthDays,
} from "../../calendar/MonthGrid";
import { registerWidgetComponent, type WidgetProps } from "./registry";
import "./calendar.css";

/**
 * Calendar widget (027): the month grid — each kind with its colour and icon, what lasts several days as a
 * bar across them — choosing a day lists it; « coming up » below.
 */
interface MonthData {
  month: string;
  today: string;
  entries: CalEntry[];
  upcoming: CalEntry[];
}

function EntryRow({ entry }: { entry: CalEntry }) {
  const format = useFormat();
  const category = categoryOf(entry);
  return (
    <li className="cal-widget__entry" data-category={category}>
      <span className="cal-widget__icon" aria-hidden="true">
        <Icon name={CATEGORY_ICONS[category] ?? "calendar"} size={12} />
      </span>
      <Link to={entry.route}>{entry.title}</Link>
      <span className="cal-widget__when">
        {entry.time ? format.dateTime(entry.time) : format.date(`${entry.date}T12:00:00Z`)}
        {entry.end > entry.date ? ` → ${format.date(`${entry.end}T12:00:00Z`)}` : ""}
      </span>
    </li>
  );
}

/** 027 (#36): this week, a day each — its number, today marked, a dot per kind of thing on it. */
function WeekStrip({ today, entries }: { today: string; entries: CalEntry[] }) {
  const base = new Date(`${today}T12:00:00Z`);
  const monday = new Date(base.getTime() - ((base.getUTCDay() + 6) % 7) * 86_400_000);
  const days = Array.from({ length: 7 }, (_, i) => new Date(monday.getTime() + i * 86_400_000));
  return (
    <Link to="/calendar" className="cal-week">
      {days.map((day) => {
        const iso = day.toISOString().slice(0, 10);
        const kinds = [...new Set(entries.filter((e) => e.date <= iso && e.end >= iso).map(categoryOf))];
        return (
          <span key={iso} className="cal-week__day" data-today={iso === today || undefined}>
            <small>{day.toLocaleDateString(undefined, { weekday: "narrow", timeZone: "UTC" })}</small>
            <strong>{day.getUTCDate()}</strong>
            <span className="cal-week__dots" aria-hidden="true">
              {kinds.slice(0, 3).map((kind) => (
                <span key={kind} data-category={kind} />
              ))}
            </span>
          </span>
        );
      })}
    </Link>
  );
}

function MonthCalendar({ payload, rows }: WidgetProps) {
  const t = useT();
  const data = (payload.data ?? {}) as Partial<MonthData>;
  const [picked, setPicked] = useState<string | null>(null);
  const month = data.month ?? new Date().toISOString().slice(0, 10);
  const days = useMemo(() => monthDays(month), [month]);
  const entries = data.entries ?? [];
  const shown = picked ? entries.filter((e) => e.date <= picked && e.end >= picked) : (data.upcoming ?? []);
  // 027 (#36): too low for the month — this week (and what comes up when there is room)
  if (rows !== undefined && rows < 5)
    return (
      <div className="cal-widget cal-widget--week">
        <WeekStrip today={data.today ?? month} entries={entries} />
        {rows > 1 && shown.length ? (
          <ul className="cal-widget__list">
            {shown.map((entry) => (
              <EntryRow key={`${entry.date}-${entry.kind}-${entry.title}`} entry={entry} />
            ))}
          </ul>
        ) : null}
      </div>
    );
  return (
    <div className="cal-widget">
      <div className="cal-widget__head">
        <p className="cal-widget__month">
          {new Date(`${month.slice(0, 7)}-01T12:00:00Z`).toLocaleDateString(undefined, {
            month: "long",
            year: "numeric",
            timeZone: "UTC",
          })}
        </p>
        <Link to="/calendar" className="cal-widget__open">
          <Icon name="calendar" size={14} />
          {t("calendar:widget.month.open")}
        </Link>
      </div>
      <MonthGrid
        days={days}
        month={month}
        today={data.today ?? ""}
        entries={entries}
        compact
        picked={picked}
        onPick={setPicked}
      />
      <CalendarLegend entries={entries} />
      <p className="cal-widget__heading">
        {picked
          ? new Date(`${picked}T12:00:00Z`).toLocaleDateString(undefined, {
              dateStyle: "full",
              timeZone: "UTC",
            })
          : t("calendar:widget.month.next")}
      </p>
      {shown.length ? (
        <ul className="cal-widget__list">
          {shown.map((entry) => (
            <EntryRow key={`${entry.date}-${entry.kind}-${entry.title}`} entry={entry} />
          ))}
        </ul>
      ) : (
        <p className="cal-widget__none">{t("calendar:widget.month.none")}</p>
      )}
    </div>
  );
}

registerWidgetComponent("calendar.month", MonthCalendar);
