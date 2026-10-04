import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMeasures } from "../../media/insights/api";

/**
 * Charts of the « media statistics » widget (027), loaded on demand: bars or an area over time, or a donut
 * by kind. A short text summary always comes with them (the chart never carries meaning alone).
 */
export interface StatsPoint {
  date: string;
  seconds: number;
  plays: number;
}

const KIND_COLORS = [
  "var(--color-accent)",
  "var(--color-accent-alt)",
  "color-mix(in oklab, var(--color-accent) 50%, var(--color-text-muted))",
  "color-mix(in oklab, var(--color-accent-alt) 50%, var(--color-text))",
  "var(--color-text-muted)",
];

function color(index: number): string {
  return KIND_COLORS[index % KIND_COLORS.length] ?? "var(--color-accent)";
}

export default function MediaStatsChart({
  chart,
  metric,
  unit,
  timeline,
  byKind,
}: {
  chart: "bars" | "area" | "donut";
  metric: "time" | "plays";
  unit: string;
  timeline: StatsPoint[];
  byKind: Array<{ kind: string; seconds: number; plays: number }>;
}) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const value = (p: { seconds: number; plays: number }) =>
    metric === "time" ? Math.round((p.seconds / 3600) * 10) / 10 : p.plays;
  const show = (n: number) =>
    metric === "time" ? measures.duration(n * 3600) : t("media:insights.plays", { count: n });
  const label = (iso: string) =>
    unit === "month"
      ? new Date(iso).toLocaleDateString(undefined, { month: "short" })
      : format.date(iso, "short");
  const tooltip = {
    contentStyle: { background: "var(--color-surface-raised)", border: "1px solid var(--color-border)" },
  };
  if (chart === "donut") {
    const rows = byKind.map((k) => ({ name: t(`media:insights.kind.${k.kind}`), value: value(k) }));
    return (
      <div className="widget-media-stats__donut">
        <ResponsiveContainer width="100%" height={150}>
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="name"
              innerRadius="58%"
              outerRadius="92%"
              isAnimationActive={false}
            >
              {rows.map((row, index) => (
                <Cell key={row.name} fill={color(index)} stroke="var(--color-surface)" />
              ))}
            </Pie>
            <Tooltip formatter={(v) => show(Number(v))} {...tooltip} />
          </PieChart>
        </ResponsiveContainer>
        <ul className="widget-media-stats__legend">
          {rows.map((row, index) => (
            <li key={row.name}>
              <span className="widget-media-stats__swatch" style={{ background: color(index) }} />
              {row.name} · {show(row.value)}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  const rows = timeline.map((p) => ({ date: p.date, value: value(p) }));
  return (
    <ResponsiveContainer width="100%" height={130}>
      {chart === "area" ? (
        <AreaChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="media-stats-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.55} />
              <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tickFormatter={label}
            stroke="var(--color-text-muted)"
            fontSize={11}
            minTickGap={28}
          />
          <Tooltip labelFormatter={(v) => label(String(v))} formatter={(v) => show(Number(v))} {...tooltip} />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--color-accent)"
            strokeWidth={2}
            fill="url(#media-stats-area)"
            isAnimationActive={false}
          />
        </AreaChart>
      ) : (
        <BarChart data={rows} margin={{ top: 6, right: 4, bottom: 0, left: 4 }}>
          <XAxis
            dataKey="date"
            tickFormatter={label}
            stroke="var(--color-text-muted)"
            fontSize={11}
            minTickGap={28}
          />
          <Tooltip labelFormatter={(v) => label(String(v))} formatter={(v) => show(Number(v))} {...tooltip} />
          <Bar dataKey="value" fill="var(--color-accent)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
        </BarChart>
      )}
    </ResponsiveContainer>
  );
}
