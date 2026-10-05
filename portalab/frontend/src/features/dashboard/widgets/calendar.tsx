import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { registerWidgetComponent, type WidgetProps } from "./registry";
import "./calendar.css";

/**
 * Calendar widget (027): the month as a grid — a mark per kind on the days with something (portal events,
 * maintenance, news, media releases), today highlighted — choosing a day lists it; « coming up » below.
 */
interface Entry {
  title: string;
  kind: string;
  time: string | null;
  route: string;
  date: string;
}

interface MonthData {
  month: string;
  today: string;
  days: Record<string, Entry[]>;
  upcoming: Entry[];
}

function iso(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function EntryRow({ entry }: { entry: Entry }) {
  const format = useFormat();
  return (
    <li className="cal-widget__entry" data-kind={entry.kind}>
      <span className="cal-widget__dot" aria-hidden="true" />
      <Link to={entry.route}>{entry.title}</Link>
      <span className="cal-widget__when">
        {entry.time ? format.dateTime(entry.time) : format.date(entry.date)}
      </span>
    </li>
  );
}

function MonthCalendar({ payload }: WidgetProps) {
  const t = useT();
  const data = (payload.data ?? {}) as Partial<MonthData>;
  const [picked, setPicked] = useState<string | null>(null);
  const monthKey = data.month ?? iso(new Date()).slice(0, 7);
  const month = new Date(`${monthKey.slice(0, 7)}-01T00:00:00`);
  const days = data.days ?? {};
  const cells = useMemo(() => {
    const first = new Date(`${monthKey.slice(0, 7)}-01T00:00:00`);
    const offset = (first.getDay() + 6) % 7; // weeks start on Monday
    const count = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
    return [
      ...Array.from({ length: offset }, (_, i) => ({ key: `pad-${i}`, day: null as Date | null })),
      ...Array.from({ length: count }, (_, i) => {
        const day = new Date(first.getFullYear(), first.getMonth(), i + 1);
        return { key: iso(day), day };
      }),
    ];
  }, [monthKey]);
  const weekdays = useMemo(() => {
    const monday = new Date(2024, 0, 1);
    return Array.from({ length: 7 }, (_, i) => ({
      key: `weekday-${i}`,
      name: new Date(monday.getTime() + i * 86_400_000).toLocaleDateString(undefined, { weekday: "narrow" }),
    }));
  }, []);
  const shown = picked ? (days[picked] ?? []) : (data.upcoming ?? []);
  return (
    <div className="cal-widget">
      <p className="cal-widget__month">
        {month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
      </p>
      <div className="cal-widget__grid">
        {weekdays.map((weekday) => (
          <span key={weekday.key} className="cal-widget__weekday" aria-hidden="true">
            {weekday.name}
          </span>
        ))}
        {cells.map(({ key, day }) => {
          if (!day) return <span key={key} aria-hidden="true" />;
          const date = iso(day);
          const items = days[date] ?? [];
          const kinds = [...new Set(items.map((item) => item.kind))].slice(0, 3);
          return (
            <button
              key={key}
              type="button"
              className="cal-widget__day"
              data-today={date === data.today || undefined}
              data-busy={items.length ? "true" : undefined}
              aria-pressed={picked === date}
              aria-label={`${day.toLocaleDateString(undefined, { day: "numeric", month: "long" })}${
                items.length ? ` · ${items.length}` : ""
              }`}
              onClick={() => setPicked(picked === date ? null : date)}
            >
              <span>{day.getDate()}</span>
              {kinds.length ? (
                <span className="cal-widget__marks" aria-hidden="true">
                  {kinds.map((kind) => (
                    <span key={kind} data-kind={kind} />
                  ))}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      <p className="cal-widget__heading">
        {picked
          ? new Date(`${picked}T00:00:00`).toLocaleDateString(undefined, { dateStyle: "full" })
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
