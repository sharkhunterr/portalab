import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { AdminTabs } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { Value } from "../api";

type Sources = components["schemas"]["MySourcesOut"];
type Streak = components["schemas"]["MyStreakOut"];

// each source keeps its colour and icon everywhere (theme tokens; the legend names it, never colour alone)
export const SOURCES: Record<string, { color: string; icon: string }> = {
  media: { color: "var(--cal-movie)", icon: "play" },
  quests: { color: "var(--cal-event)", icon: "target" },
  streak: { color: "var(--rarity-legendary)", icon: "flame" },
  campaigns: { color: "var(--cal-campaign)", icon: "star" },
  achievements: { color: "var(--rarity-epic)", icon: "trophy" },
  shop: { color: "var(--cal-book)", icon: "shop" },
  support: { color: "var(--cal-series)", icon: "lifebuoy" },
  visits: { color: "var(--color-accent-alt)", icon: "home" },
  levels: { color: "var(--rarity-rare)", icon: "gift" },
  pace: { color: "var(--color-accent)", icon: "trending" },
  activity: { color: "var(--cal-news)", icon: "zap" },
  other: { color: "var(--cal-other)", icon: "sparkles" },
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

/**
 * Where my gains come from (027, progression page): the share of each source — plays, quests, streak and
 * campaign bonuses, achievements, the shop, support… — as a ring, and day by day as stacked bars; my
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
            label={t("gamification:sources.value")}
            current={value}
            onChange={(next) => setValue(next as Value)}
            tabs={VALUES.map((v) => ({ key: v, label: t(`gamification:value.${v}`) }))}
          />
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
      {data && !sources.length ? <p className="admin-muted">{t("gamification:sources.empty")}</p> : null}
      {sources.length ? (
        <div className="gain-sources__charts">
          <figure className="gain-sources__ring">
            <div aria-hidden="true" className="gain-sources__ring-plot">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={sources}
                    dataKey="amount"
                    nameKey="source"
                    innerRadius="58%"
                    outerRadius="90%"
                    paddingAngle={2}
                  >
                    {sources.map((s) => (
                      <Cell
                        key={s.source}
                        fill={SOURCES[s.source]?.color ?? "var(--cal-other)"}
                        stroke="none"
                      />
                    ))}
                  </Pie>
                  <Tooltip formatter={(amount, source) => [`${amount} ${unit}`, label(String(source))]} />
                </PieChart>
              </ResponsiveContainer>
              <span className="gain-sources__total">
                <strong>{format.number(data?.total ?? 0)}</strong>
                <span>{unit}</span>
              </span>
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
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={bars}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="day" stroke="var(--color-text-muted)" fontSize={12} />
                  <YAxis stroke="var(--color-text-muted)" fontSize={12} width={44} />
                  <Tooltip />
                  {keys.map((key, index) => (
                    <Bar
                      key={key}
                      dataKey={key}
                      name={label(key)}
                      stackId="gains"
                      fill={SOURCES[key]?.color ?? "var(--cal-other)"}
                      radius={index === keys.length - 1 ? [3, 3, 0, 0] : 0}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </figure>
        </div>
      ) : null}
      {sources.length ? (
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
      {table && data ? (
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
