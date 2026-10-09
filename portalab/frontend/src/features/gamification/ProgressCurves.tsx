import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import type { WidgetProps } from "../dashboard/widgets/registry";
import { ProgressBoosts } from "./widget";

/**
 * « My progression » as curves (027, #31 — a look sold in the shop): what I gained day by day over the last
 * 30 days, summed up as a rising curve — XP, Coins or Contribution, one at a time — with the total and
 * what boosts my gains now. Loaded on demand (the chart library stays out of the dashboard's bundle).
 */
type Value = "xp" | "coins" | "contribution";
const VALUES: Value[] = ["xp", "coins", "contribution"];
const VALUE_ICON: Record<Value, string> = { xp: "sparkles", coins: "coins", contribution: "heart" };
const DAYS = 30;

interface Sources {
  total: number;
  days: { day: string; amounts: Record<string, number> }[];
}

/** Each day of the period (a day without gains counts 0), the gains summed up from the first. */
export function cumulate(days: Sources["days"], today: Date, span = DAYS): { day: string; total: number }[] {
  const byDay = new Map(
    days.map((d) => [d.day.slice(0, 10), Object.values(d.amounts).reduce((a, b) => a + b, 0)]),
  );
  const out: { day: string; total: number }[] = [];
  let running = 0;
  for (let back = span - 1; back >= 0; back -= 1) {
    const day = new Date(today.getTime() - back * 86_400_000).toISOString().slice(0, 10);
    running += byDay.get(day) ?? 0;
    out.push({ day, total: running });
  }
  return out;
}

export default function ProgressCurves({ payload }: WidgetProps) {
  const t = useT();
  const format = useFormat();
  const gradient = `curves-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const [value, setValue] = useState<Value>("xp");
  const level = ((payload.data ?? {}) as { level?: number }).level ?? 1;
  const sources = useQuery({
    queryKey: ["gamification", "sources", value, DAYS],
    queryFn: async () =>
      (await api.GET("/api/v1/me/progression/sources", { params: { query: { value, days: DAYS } } }))
        .data as Sources,
  }).data;
  const points = sources ? cumulate(sources.days, new Date()) : [];
  const gained = points.at(-1)?.total ?? 0;
  const unit = t(`gamification:value.${value}`);
  return (
    <div className="widget-curves">
      <div className="widget-curves__head">
        <Link to="/progression" className="widget-curves__level">
          <Icon name="trophy" size={14} />
          {t("gamification:level", { level })}
        </Link>
        <span className="widget-curves__gained">
          {t("gamification:widget.progress.gained", { amount: format.number(gained), unit, days: DAYS })}
        </span>
        <span className="widget-curves__values">
          {VALUES.map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={v === value}
              onClick={() => setValue(v)}
              aria-label={t(`gamification:value.${v}`)}
              title={t(`gamification:value.${v}`)}
            >
              <Icon name={VALUE_ICON[v]} size={13} />
            </button>
          ))}
        </span>
      </div>
      <div className="widget-curves__chart" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
            <defs>
              <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.5} />
                <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            {/* no axis: the period is in the head, each day in the tooltip — the curve keeps the room */}
            <XAxis dataKey="day" hide />
            <Tooltip
              formatter={(amount) => [`${format.number(Number(amount))} ${unit}`, ""]}
              labelFormatter={(day) => format.date(`${String(day)}T12:00:00`, "medium")}
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
              }}
            />
            <Area
              type="monotone"
              dataKey="total"
              stroke="var(--color-accent)"
              strokeWidth={2.5}
              fill={`url(#${gradient})`}
              isAnimationActive
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <ProgressBoosts />
    </div>
  );
}
