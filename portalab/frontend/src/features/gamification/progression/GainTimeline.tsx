import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";

type Timeline = components["schemas"]["MyTimelineOut"];

// each value keeps its colour (theme tokens); the legend and the cards name them, never colour alone
const SHOWN_LEVEL_UPS = 12; // the latest; the chart marks every one

const LINES = [
  { key: "xp", color: "var(--color-accent)", axis: "xp" },
  { key: "coins", color: "var(--rarity-legendary)", axis: "other" },
  { key: "contribution", color: "var(--color-accent-alt)", axis: "other" },
] as const;

export function useTimeline(days: number) {
  return useQuery({
    queryKey: ["gamification", "timeline", days],
    queryFn: async () =>
      (await api.GET("/api/v1/me/progression/timeline", { params: { query: { days } } })).data as Timeline,
  });
}

/** Every day of the period, those without gains at zero — so the lines say « nothing » rather than skip. */
export function fillDays(timeline: Timeline | undefined, days: number, today = new Date()) {
  const known = new Map((timeline?.days ?? []).map((d) => [d.day, d]));
  return Array.from({ length: days + 1 }, (_, i) => {
    const day = new Date(today.getTime() - (days - i) * 86_400_000).toISOString().slice(0, 10);
    const found = known.get(day);
    return { day, xp: found?.xp ?? 0, coins: found?.coins ?? 0, contribution: found?.contribution ?? 0 };
  });
}

/**
 * #62: my progression over time — XP, Coins and Contribution gained day by day as lines (XP on its own
 * axis: it counts far more), the days I reached a level marked on the chart and told as small cards below.
 */
export function GainTimeline({ days }: { days: number }) {
  const t = useT();
  const format = useFormat();
  const timeline = useTimeline(days).data;
  const points = fillDays(timeline, days);
  const ups = timeline?.level_ups ?? [];
  const short = (day: string) => {
    const { day: d, month } = format.dayMonth(`${day}T12:00:00Z`);
    return `${d} ${month}`;
  };
  const compact = (value: number) => format.compact(value);
  return (
    <div className="gain-timeline">
      <figure className="gain-sources__bars">
        <figcaption>{t("gamification:sources.timeline")}</figcaption>
        <div aria-hidden="true">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={points} margin={{ top: 16, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="day"
                tickFormatter={short}
                stroke="var(--color-text-muted)"
                fontSize={12}
                minTickGap={24}
              />
              <YAxis
                yAxisId="xp"
                stroke="var(--color-text-muted)"
                fontSize={12}
                width={44}
                tickFormatter={compact}
              />
              <YAxis
                yAxisId="other"
                orientation="right"
                stroke="var(--color-text-muted)"
                fontSize={12}
                width={40}
                tickFormatter={compact}
              />
              <Tooltip
                labelFormatter={(value) => short(String(value))}
                formatter={(value, name) => [format.number(Number(value)), name]}
                contentStyle={{
                  background: "var(--color-surface-raised)",
                  border: "1px solid var(--color-border)",
                }}
              />
              <Legend />
              {ups.map((up) => (
                <ReferenceLine
                  key={up.level}
                  x={up.day}
                  yAxisId="xp"
                  stroke="var(--rarity-epic)"
                  strokeDasharray="4 3"
                  label={{
                    value: String(up.level),
                    position: "top",
                    fill: "var(--rarity-epic)",
                    fontSize: 11,
                  }}
                />
              ))}
              {LINES.map((line) => (
                <Line
                  key={line.key}
                  yAxisId={line.axis}
                  type="monotone"
                  dataKey={line.key}
                  name={t(`gamification:value.${line.key}`)}
                  stroke={line.color}
                  strokeWidth={line.key === "xp" ? 2.5 : 1.8}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </figure>
      {ups.length ? (
        <section className="gain-levelups" aria-label={t("gamification:sources.levelUps")}>
          <h3>
            <Icon name="trophy" size={16} /> {t("gamification:sources.levelUps")}
          </h3>
          <ol>
            {[...ups]
              .reverse()
              .slice(0, SHOWN_LEVEL_UPS)
              .map((up) => (
                <li key={up.level} className="gain-levelup">
                  <span className="gain-levelup__level">{format.number(up.level)}</span>
                  <span className="gain-levelup__text">
                    <strong>{t("gamification:level", { level: up.level })}</strong>
                    <small>{format.dateTime(up.at)}</small>
                  </span>
                </li>
              ))}
            {ups.length > SHOWN_LEVEL_UPS ? (
              <li className="gain-levelup gain-levelup--more">
                {t("gamification:sources.moreLevelUps", { count: ups.length - SHOWN_LEVEL_UPS })}
              </li>
            ) : null}
          </ol>
        </section>
      ) : (
        <p className="admin-muted">{t("gamification:sources.noLevelUp")}</p>
      )}
    </div>
  );
}
