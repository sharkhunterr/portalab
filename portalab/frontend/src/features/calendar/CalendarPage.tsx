import { useId, useMemo, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { SelectField } from "../../design-system/components/Field";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { type CalendarItem, useCalendar, useReminderActions, useReminders } from "./api";
import "./calendar.css";

/**
 * Calendar (spec 011 T025): month, week and list views of items owned by other domains. Every type has an
 * icon **and** a text label (never color alone); a source that does not answer gets its own banner while the
 * others render; times follow the user's time zone and first day of the week (026); reminders are opt-in.
 */
type View = "month" | "week" | "list";
const ICONS: Record<string, string> = {
  maintenance: "🔧",
  publication: "📰",
  campaign: "🏁",
  community_event: "👥",
  deadline: "⏳",
  event: "📅",
};
const DAY = 86_400_000;

function dayKey(value: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(value);
}

export function itemDay(item: CalendarItem, timeZone: string): string {
  if (item.date) return item.date;
  return item.starts_at ? dayKey(new Date(item.starts_at), timeZone) : "";
}

function startOfDayUtc(key: string): Date {
  return new Date(`${key}T00:00:00Z`);
}

export function range(
  view: View,
  anchor: string,
  firstDay: number,
): { from: Date; to: Date; days: string[] } {
  const base = startOfDayUtc(anchor);
  let start: Date;
  let count: number;
  if (view === "month") {
    const first = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth(), 1));
    const offset = (first.getUTCDay() + 6 - firstDay + 7) % 7; // 0 = Monday … 6 = Sunday
    start = new Date(first.getTime() - offset * DAY);
    count = 42;
  } else if (view === "week") {
    const offset = (base.getUTCDay() + 6 - firstDay + 7) % 7;
    start = new Date(base.getTime() - offset * DAY);
    count = 7;
  } else {
    start = base;
    count = 30;
  }
  const days = Array.from({ length: count }, (_, i) =>
    new Date(start.getTime() + i * DAY).toISOString().slice(0, 10),
  );
  // one extra day on both ends covers every time zone offset
  return { from: new Date(start.getTime() - DAY), to: new Date(start.getTime() + (count + 1) * DAY), days };
}

function ItemLine({ item, leads }: { item: CalendarItem; leads: number[] }) {
  const t = useT();
  const format = useFormat();
  const { add } = useReminderActions();
  const [lead, setLead] = useState(String(leads[0] ?? 60));
  const route = item.url_ref?.startsWith("/") ? item.url_ref : null;
  const future = item.starts_at ? new Date(item.starts_at).getTime() > Date.now() : false;
  return (
    <li className="calendar-item" data-type={item.type}>
      <span aria-hidden="true">{ICONS[item.type] ?? "📅"} </span>
      <span className="calendar-item__type">{t(`calendar:type.${item.type}`)}</span> ·{" "}
      {route ? <Link to={route}>{item.title}</Link> : item.title}
      {item.starts_at && !item.all_day ? (
        <span className="calendar-item__time"> · {format.time(item.starts_at)}</span>
      ) : null}
      {item.status !== "scheduled" && item.status !== "published" ? (
        <span className="calendar-item__status"> · {item.status}</span>
      ) : null}
      {future ? (
        <span className="calendar-item__remind">
          <SelectField
            label={t("calendar:remindBefore")}
            value={lead}
            onChange={(e) => setLead(e.target.value)}
          >
            {leads.map((minutes) => (
              <option key={minutes} value={minutes}>
                {t("calendar:lead", { minutes })}
              </option>
            ))}
          </SelectField>
          <Button
            variant="secondary"
            onClick={() =>
              add.mutate({
                source_kind: item.source_kind,
                source_id: item.source_id,
                lead_minutes: Number(lead),
              })
            }
          >
            {t("calendar:remind")}
            <span className="visually-hidden">: {item.title}</span>
          </Button>
        </span>
      ) : null}
    </li>
  );
}

export function CalendarPage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const ctx = useLocaleContext();
  const timeZone = ctx.time_zone || "UTC";
  const firstDay = ctx.first_day_of_week ?? 0;
  const [view, setView] = useState<View>("month");
  const [anchor, setAnchor] = useState(() => dayKey(new Date(), timeZone));
  const { from, to, days } = useMemo(() => range(view, anchor, firstDay), [view, anchor, firstDay]);
  const calendar = useCalendar(from, to);
  const reminders = useReminders();
  const byDay = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    for (const item of calendar.data?.items ?? []) {
      const key = itemDay(item, timeZone);
      map.set(key, [...(map.get(key) ?? []), item]);
    }
    return map;
  }, [calendar.data, timeZone]);
  const move = (direction: number) => {
    const step = view === "month" ? 30 : view === "week" ? 7 : 30;
    setAnchor(new Date(startOfDayUtc(anchor).getTime() + direction * step * DAY).toISOString().slice(0, 10));
  };
  const leads = calendar.data?.lead_options ?? [60];
  const failing = Object.entries(calendar.data?.source_states ?? {}).filter(([, state]) => state !== "ok");
  const types = [...new Set((calendar.data?.items ?? []).map((i) => i.type))];
  return (
    <section aria-labelledby={headingId} className="calendar-page">
      <h2 id={headingId}>{t("calendar:title")}</h2>
      <div className="ds-stack ds-stack--row" role="toolbar" aria-label={t("calendar:navigation")}>
        {(["month", "week", "list"] as View[]).map((v) => (
          <Button
            key={v}
            variant={v === view ? "primary" : "secondary"}
            aria-pressed={v === view}
            onClick={() => setView(v)}
          >
            {t(`calendar:view.${v}`)}
          </Button>
        ))}
        <Button variant="secondary" onClick={() => move(-1)}>
          {t("calendar:previous")}
        </Button>
        <Button variant="secondary" onClick={() => setAnchor(dayKey(new Date(), timeZone))}>
          {t("calendar:today")}
        </Button>
        <Button variant="secondary" onClick={() => move(1)}>
          {t("calendar:next")}
        </Button>
      </div>
      {failing.map(([kind]) => (
        <p key={kind} role="status" className="calendar-banner">
          {t("calendar:sourceUnavailable", { source: t(calendar.data?.sources[kind] ?? kind) })}
        </p>
      ))}
      {types.length ? (
        <ul className="calendar-legend" aria-label={t("calendar:legend")}>
          {types.map((type) => (
            <li key={type}>
              <span aria-hidden="true">{ICONS[type] ?? "📅"}</span> {t(`calendar:type.${type}`)}
            </li>
          ))}
        </ul>
      ) : null}
      {calendar.isPending ? <FunctionalState state="loading" /> : null}
      {calendar.isError ? <FunctionalState state="unavailable" onRetry={() => calendar.refetch()} /> : null}
      {calendar.data ? (
        view === "list" ? (
          <ol className="calendar-list">
            {days
              .filter((day) => byDay.has(day))
              .map((day) => (
                <li key={day}>
                  <h3>{format.date(`${day}T12:00:00Z`, "long")}</h3>
                  <ul>
                    {(byDay.get(day) ?? []).map((item) => (
                      <ItemLine key={`${item.source_kind}-${item.source_id}`} item={item} leads={leads} />
                    ))}
                  </ul>
                </li>
              ))}
            {days.every((day) => !byDay.has(day)) ? <li>{t("calendar:empty")}</li> : null}
          </ol>
        ) : (
          <ol className={`calendar-grid calendar-grid--${view}`}>
            {days.map((day) => (
              <li key={day} className="calendar-day" data-today={day === dayKey(new Date(), timeZone)}>
                <h3 className="calendar-day__label">{format.date(`${day}T12:00:00Z`, "short")}</h3>
                <ul>
                  {(byDay.get(day) ?? []).map((item) => (
                    <ItemLine key={`${item.source_kind}-${item.source_id}`} item={item} leads={leads} />
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        )
      ) : null}
      {reminders.data?.length ? (
        <section aria-label={t("calendar:myReminders")}>
          <h3>{t("calendar:myReminders")}</h3>
          <ul>
            {reminders.data.map((r) => (
              <li key={r.id}>
                {r.title} · {format.dateTime(r.remind_at)} · {t(`calendar:reminderStatus.${r.status}`)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

export default CalendarPage;
