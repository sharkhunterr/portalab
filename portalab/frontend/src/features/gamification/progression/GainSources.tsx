import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { AdminTabs } from "../../../design-system/admin/AdminKit";
import { BarsChart } from "../../../design-system/charts/Charts";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Value } from "../api";
import { GainTimeline } from "./GainTimeline";

type Sources = components["schemas"]["MySourcesOut"];
type Streak = components["schemas"]["MyStreakOut"];

// each source keeps its colour and icon everywhere (theme tokens; the legend names it, never colour alone)
export const SOURCES: Record<string, { color: string; icon: string }> = {
  // issue 125: one colour each — the chart series' hues, so two sources never look alike side by side
  media: { color: "var(--chart-3)", icon: "play" },
  // issue 160: plays by kind — the media family's hue, each kind its own shade and icon
  episode: { color: "color-mix(in oklab, var(--chart-3) 80%, var(--chart-1))", icon: "tv" },
  movie: { color: "color-mix(in oklab, var(--chart-3) 55%, black)", icon: "film" },
  live: { color: "color-mix(in oklab, var(--chart-3) 45%, var(--chart-9))", icon: "radio" },
  book: { color: "color-mix(in oklab, var(--chart-4) 55%, var(--chart-7))", icon: "book" },
  audiobook: { color: "color-mix(in oklab, var(--chart-7) 60%, white)", icon: "headphones" },
  music: { color: "color-mix(in oklab, var(--chart-2) 50%, var(--chart-10))", icon: "music" },
  game: { color: "color-mix(in oklab, var(--chart-6) 50%, var(--chart-8))", icon: "gamepad" },
  requests: { color: "color-mix(in oklab, var(--chart-6) 55%, white)", icon: "inbox" }, // issue 129
  quests: { color: "var(--chart-8)", icon: "target" },
  streak: { color: "var(--chart-2)", icon: "flame" },
  campaigns: { color: "var(--chart-9)", icon: "star" },
  achievements: { color: "var(--chart-5)", icon: "trophy" },
  shop: { color: "var(--chart-6)", icon: "shop" },
  support: { color: "var(--chart-4)", icon: "lifebuoy" },
  visits: { color: "var(--chart-10)", icon: "home" },
  levels: { color: "var(--chart-7)", icon: "gift" },
  wheel: { color: "color-mix(in oklab, var(--chart-7) 55%, var(--chart-9))", icon: "ferris-wheel" }, // issue 225
  pace: { color: "var(--chart-1)", icon: "trending" },
  boost: { color: "color-mix(in oklab, var(--chart-5) 58%, white)", icon: "rocket" }, // #55: bought in the shop
  activity: { color: "color-mix(in oklab, var(--chart-8) 58%, white)", icon: "zap" },
  other: { color: "var(--cal-maintenance)", icon: "sparkles" },
  admin: { color: "color-mix(in oklab, var(--cal-maintenance) 60%, black)", icon: "shield" }, // issue 107
};
const PERIODS = [7, 30, 90, 365];
const VALUES: Value[] = ["xp", "coins"];

function useSources(value: Value, days: number) {
  return useQuery({
    queryKey: ["gamification", "sources", value, days],
    queryFn: async () =>
      (await api.GET("/api/v1/me/progression/sources", { params: { query: { value, days } } }))
        .data as Sources,
  });
}

function useStreak() {
  return useQuery({
    queryKey: ["gamification", "my-streak"],
    queryFn: async () => (await api.GET("/api/v1/me/streak")).data as Streak,
    staleTime: 60_000,
  });
}

/** Axis ticks: 1.2k, 500k, 3M — never cut. */

/**
 * Where my gains come from (027, progression page): the share of each source — plays, quests, streak and
 * campaign bonuses, achievements, the shop, support… — as one stacked bar, and day by day as stacked bars; my
 * current play streak beside it. A table alternative is one click away.
 */
export function GainSources() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const tableId = useId();
  const [value, setValue] = useState<Value>("xp");
  const [days, setDays] = useState(30);
  const [table, setTable] = useState(false);
  // #62: by source, or over time; issue 114: or my XP in all, day after day
  const [mode, setMode] = useState<"sources" | "timeline" | "total">("sources");
  const data = useSources(value, days).data;
  const streak = useStreak().data;
  const unit = t(`gamification:value.${value}`);
  const label = (source: string) => t(`gamification:sources.${source}`);
  const sources = data?.sources ?? [];
  const keys = sources.map((s) => s.source);
  const bars = (data?.days ?? []).map((d) => ({ day: d.day.slice(5), ...d.amounts }));
  return (
    <section className="ds-card gain-sources" aria-labelledby={headingId}>
      <header className="gain-sources__head">
        <h2 id={headingId}>
          <Icon name="chart" size={20} /> {t("gamification:sources.title")}
        </h2>
        <div className="gain-sources__filters">
          <AdminTabs
            label={t("gamification:sources.mode")}
            current={mode}
            onChange={(next) => setMode(next as "sources" | "timeline" | "total")}
            tabs={[
              { key: "sources", label: t("gamification:sources.bySource") },
              { key: "timeline", label: t("gamification:sources.overTime") },
              { key: "total", label: t("gamification:sources.total") },
            ]}
          />
          {mode === "sources" ? (
            <AdminTabs
              label={t("gamification:sources.value")}
              current={value}
              onChange={(next) => setValue(next as Value)}
              tabs={VALUES.map((v) => ({ key: v, label: t(`gamification:value.${v}`) }))}
            />
          ) : null}
          <AdminTabs
            label={t("gamification:sources.period")}
            current={String(days)}
            onChange={(next) => setDays(Number(next))}
            tabs={PERIODS.map((p) => ({
              key: String(p),
              label: t("gamification:admin.overview.days", { days: p }),
            }))}
          />
        </div>
      </header>
      {streak?.enabled ? (
        <p className="gain-sources__streak" data-active={streak.days > 1 || undefined}>
          <Icon name="flame" size={18} />
          {streak.days > 0
            ? t("gamification:sources.streakNow", { days: streak.days, multiplier: streak.multiplier })
            : t("gamification:sources.noStreak")}
          {streak.next
            ? ` ${t("gamification:sources.nextTier", { days: streak.next.days - streak.days, multiplier: streak.next.multiplier })}`
            : ""}
        </p>
      ) : null}
      {streak?.enabled && (streak.freezes || streak.last_frozen) ? (
        <p className="gain-sources__streak" data-freeze="true">
          <Icon name="snowflake" size={18} />
          {streak.freezes
            ? `${t("gamification:freeze.owned", { count: streak.freezes })} — ${t("gamification:freeze.hint")}`
            : null}
          {streak.last_frozen
            ? ` ${t("gamification:freeze.used", { date: format.date(streak.last_frozen) })}`
            : null}
        </p>
      ) : null}
      {mode === "timeline" ? <GainTimeline days={days} /> : null}
      {mode === "total" ? <GainTimeline days={days} cumulative /> : null}
      {mode === "sources" && data && !sources.length ? (
        <p className="admin-muted">{t("gamification:sources.empty")}</p>
      ) : null}
      {mode === "sources" && sources.length ? (
        <div className="gain-sources__charts">
          <figure className="gain-stack">
            <p className="gain-stack__total">
              <strong>{format.number(data?.total ?? 0)}</strong> {unit}
            </p>
            <div
              className="gain-stack__bar"
              role="img"
              aria-label={sources.map((s) => `${label(s.source)} ${s.amount}`).join(", ")}
            >
              {sources.map((s) => (
                <span
                  key={s.source}
                  className="gain-stack__part"
                  title={`${label(s.source)} · ${s.amount} ${unit}`}
                  style={{
                    inlineSize: `${(s.amount / Math.max(1, data?.total ?? 1)) * 100}%`,
                    background: SOURCES[s.source]?.color ?? "var(--cal-other)",
                  }}
                />
              ))}
            </div>
            <figcaption>
              <ul className="gain-sources__legend">
                {sources.map((s) => (
                  <li key={s.source}>
                    <span
                      className="gain-sources__dot"
                      style={{ background: SOURCES[s.source]?.color }}
                      aria-hidden="true"
                    >
                      <Icon name={SOURCES[s.source]?.icon ?? "sparkles"} size={12} />
                    </span>
                    <span>{label(s.source)}</span>
                    <strong>
                      {format.number(s.amount)}{" "}
                      <span className="admin-muted">
                        ({Math.round((s.amount / Math.max(1, data?.total ?? 1)) * 100)} %)
                      </span>
                    </strong>
                  </li>
                ))}
              </ul>
            </figcaption>
          </figure>
          <figure className="gain-sources__bars">
            <figcaption>{t("gamification:sources.daily", { unit })}</figcaption>
            <div aria-hidden="true">
              <BarsChart
                data={bars}
                x="day"
                stacked
                height={240}
                legend={false}
                format={(value) => format.number(value)}
                series={keys.map((key) => ({
                  key,
                  label: label(key),
                  color: SOURCES[key]?.color ?? "var(--cal-other)",
                }))}
              />
            </div>
          </figure>
        </div>
      ) : null}
      {mode === "sources" && sources.length ? (
        <Button
          variant="ghost"
          onClick={() => setTable(!table)}
          aria-expanded={table}
          aria-controls={tableId}
        >
          <Icon name="list" size={16} />
          {table ? t("gamification:admin.overview.hideTable") : t("gamification:admin.overview.showTable")}
        </Button>
      ) : null}
      {mode === "sources" && table && data ? (
        <table id={tableId} className="admin-table" aria-label={t("gamification:sources.title")}>
          <thead>
            <tr>
              <th scope="col">{t("gamification:admin.overview.day")}</th>
              {keys.map((key) => (
                <th key={key} scope="col" data-align="end">
                  {label(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.days.map((d) => (
              <tr key={d.day}>
                <td>{format.date(`${d.day}T12:00:00Z`, "medium")}</td>
                {keys.map((key) => (
                  <td key={key} data-align="end">
                    {d.amounts[key] ?? 0}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
