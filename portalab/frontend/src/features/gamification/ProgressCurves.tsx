import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { LinesChart } from "../../design-system/charts/Charts";
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
        {/* no axis: the period is in the head, each day in the tooltip — the curve keeps the room (issue 117:
            the chart kit's area) */}
        <LinesChart
          data={points}
          x="day"
          area
          height="100%"
          xAxis={false}
          yAxis={false}
          grid={false}
          legend={false}
          series={[{ key: "total", label: unit }]}
          xFormat={(day) => format.date(`${day}T12:00:00`, "medium")}
          format={(amount) => `${format.number(amount)} ${unit}`}
        />
      </div>
      <ProgressBoosts />
    </div>
  );
}
