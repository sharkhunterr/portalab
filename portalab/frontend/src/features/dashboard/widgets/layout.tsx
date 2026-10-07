import { useEffect, useState } from "react";
import { Link } from "react-router";
import { levelProgress } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { useAchievements, useProgression, useQuests } from "../../gamification/api";
import { registerWidgetComponent, type WidgetProps } from "./registry";

/**
 * 027: small widgets to lay out a dashboard — a progress bar (across or upright: level, today's objectives,
 * quests, achievements), a separator, a clock, a sticky note and a countdown. Their content is their
 * settings; progress is read where the portal already shows it, so it always agrees with the header.
 */
interface Progress {
  done: number;
  total: number;
  label: string;
  detail: string;
  icon: string;
  route: string;
}

function useProgress(metric: string): Progress | null {
  const t = useT();
  const format = useFormat();
  const progression = useProgression();
  const quests = useQuests();
  const achievements = useAchievements();
  switch (metric) {
    case "objectives":
    case "quests": {
      const list = (Array.isArray(quests.data) ? quests.data : []).filter((q) =>
        metric === "objectives" ? q.kind === "daily" : q.kind !== "daily",
      );
      if (!quests.data) return null;
      const done = list.filter((q) => q.completed).length;
      return {
        done,
        total: list.length,
        label: t(`dashboard:progress.${metric}`),
        detail: `${format.number(done)} / ${format.number(list.length)}`,
        icon: metric === "objectives" ? "target" : "scroll",
        route: "/progression",
      };
    }
    case "achievements": {
      const list = Array.isArray(achievements.data) ? achievements.data : null;
      if (!list) return null;
      const done = list.filter((a) => a.state === "unlocked").length;
      return {
        done,
        total: list.length,
        label: t("dashboard:progress.achievements"),
        detail: `${format.number(done)} / ${format.number(list.length)}`,
        icon: "trophy",
        route: "/progression",
      };
    }
    default: {
      const p = progression.data;
      if (!p) return null;
      const next = p.next_level_at ?? null;
      const ratio = levelProgress(p.xp, p.level_floor, next);
      return {
        done: Math.round(ratio * 1000),
        total: 1000,
        label:
          next === null
            ? t("dashboard:progress.levelMax", { level: p.level })
            : t("dashboard:progress.level", { level: p.level }),
        detail:
          next === null
            ? format.number(p.xp)
            : `${format.number(p.xp - p.level_floor)} / ${format.number(next - p.level_floor)} XP`,
        icon: "star",
        route: "/progression",
      };
    }
  }
}

function ProgressWidget({ payload, vertical = false }: WidgetProps & { vertical?: boolean }) {
  const format = useFormat();
  const metric = String((payload.data as { metric?: string } | null)?.metric ?? "level");
  const progress = useProgress(metric);
  const ratio = progress && progress.total > 0 ? progress.done / progress.total : 0;
  const percent = format.percent(ratio);
  return (
    <Link
      to={progress?.route ?? "/progression"}
      className="widget-progress"
      data-orientation={vertical ? "vertical" : "horizontal"}
      data-metric={metric}
      data-full={ratio >= 1 || undefined}
    >
      <span className="widget-progress__label">
        <Icon name={progress?.icon ?? "gauge"} size={16} />
        <span>{progress?.label ?? "…"}</span>
      </span>
      <span
        className="widget-progress__track"
        role="progressbar"
        aria-label={progress?.label ?? ""}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
        aria-valuetext={progress ? `${progress.detail} (${percent})` : undefined}
        style={{ "--progress": ratio } as React.CSSProperties}
      >
        <span className="widget-progress__fill" />
      </span>
      <span className="widget-progress__value">
        <strong>{percent}</strong>
        <span>{progress?.detail ?? ""}</span>
      </span>
    </Link>
  );
}

function SeparatorWidget({ payload }: WidgetProps) {
  const data = (payload.data ?? {}) as { style?: string; label?: string };
  const label = String(data.label ?? "").trim();
  return (
    <div className="widget-separator" data-style={data.style ?? "gradient"}>
      <span className="widget-separator__line" aria-hidden="true" />
      {label ? <span className="widget-separator__label">{label}</span> : null}
      {label ? <span className="widget-separator__line" aria-hidden="true" /> : null}
    </div>
  );
}

function ClockWidget({ payload }: WidgetProps) {
  const ctx = useLocaleContext();
  const data = (payload.data ?? {}) as { seconds?: boolean; date?: boolean };
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), data.seconds ? 1000 : 15_000);
    return () => window.clearInterval(timer);
  }, [data.seconds]);
  const hour12 = ctx.hour_cycle === null ? undefined : ctx.hour_cycle === "h12";
  const time = new Intl.DateTimeFormat(ctx.locale, {
    hour: "2-digit",
    minute: "2-digit",
    ...(data.seconds ? { second: "2-digit" } : {}),
    timeZone: ctx.time_zone,
    ...(hour12 === undefined ? {} : { hour12 }),
  }).format(now);
  const date = new Intl.DateTimeFormat(ctx.locale, {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: ctx.time_zone,
  }).format(now);
  return (
    <div className="widget-clock">
      <time className="widget-clock__time" dateTime={now.toISOString()}>
        {time}
      </time>
      {data.date !== false ? <span className="widget-clock__date">{date}</span> : null}
    </div>
  );
}

function NoteWidget({ payload }: WidgetProps) {
  const data = (payload.data ?? {}) as { text?: string; color?: string };
  return (
    <div className="widget-note" data-color={data.color ?? "yellow"}>
      <p>{data.text}</p>
    </div>
  );
}

/** Whole days from today to a ``YYYY-MM-DD`` date, in the member's time zone. */
export function daysUntil(date: string, today: Date, timeZone?: string): number {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(timeZone ? { timeZone } : {}),
  }).format(today);
  const [y1, m1, d1] = parts.split("-").map(Number);
  const [y2, m2, d2] = date.split("-").map(Number);
  const from = Date.UTC(y1 ?? 1970, (m1 ?? 1) - 1, d1 ?? 1);
  const to = Date.UTC(y2 ?? 1970, (m2 ?? 1) - 1, d2 ?? 1);
  return Math.round((to - from) / 86_400_000);
}

function CountdownWidget({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const ctx = useLocaleContext();
  const data = (payload.data ?? {}) as { label?: string; date?: string };
  const date = String(data.date ?? "");
  const days = daysUntil(date, new Date(), ctx.time_zone ?? undefined);
  return (
    <div className="widget-countdown" data-past={days < 0 || undefined} data-today={days === 0 || undefined}>
      <strong className="widget-countdown__days">
        {days < 0
          ? t("dashboard:widget.countdown.past", { count: -days })
          : t("dashboard:widget.countdown.days", { count: days })}
      </strong>
      <span className="widget-countdown__what">
        <Icon name="hourglass" size={14} />
        {String(data.label ?? "").trim() || format.date(`${date}T12:00:00`, "medium")}
      </span>
    </div>
  );
}

registerWidgetComponent("dashboard.progress", ProgressWidget);
registerWidgetComponent("dashboard.progress_vertical", (props: WidgetProps) => (
  <ProgressWidget {...props} vertical />
));
registerWidgetComponent("dashboard.separator", SeparatorWidget);
registerWidgetComponent("dashboard.clock", ClockWidget);
registerWidgetComponent("dashboard.note", NoteWidget);
registerWidgetComponent("dashboard.countdown", CountdownWidget);
