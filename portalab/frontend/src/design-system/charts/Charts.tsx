import { type CSSProperties, type ReactNode, useId } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./charts.css";

/**
 * The chart kit (issue 117): every shape the portal draws, in one place and one look — bars (upright, lying,
 * stacked), lines and areas, a donut with its total, a gauge, a sparkline, a heatmap and a radar. Colours
 * come from the theme's tokens (``PALETTE``), numbers from the caller's ``format``; the look (axes, grid,
 * tooltips, legends) from ``charts.css``. A chart never carries meaning alone: each page says the same in
 * words or offers the table beside it.
 */
export const PALETTE = [
  "var(--color-accent)",
  "var(--color-accent-alt)",
  "var(--rarity-epic)",
  "var(--state-available-fg, var(--cal-series))",
  "var(--cal-book)",
  "var(--rarity-legendary)",
  "var(--cal-event)",
  "var(--color-text-muted)",
];
const DASHES = ["", "6 3", "2 3", "8 3 2 3"];

export function paletteColor(index: number): string {
  return PALETTE[index % PALETTE.length] ?? "var(--color-accent)";
}

export type Datum = Record<string, string | number | null | undefined>;
export interface ChartSeries {
  key: string;
  label: string;
  color?: string | undefined;
  /** told apart without colour too */
  dashed?: boolean | undefined;
}
interface Common {
  height?: number | undefined;
  /** the values as the page says them (« 1 h 20 », « 1 234 XP ») */
  format?: ((value: number) => string) | undefined;
  /** the categories or days on the axis */
  xFormat?: ((value: string) => string) | undefined;
  legend?: boolean | undefined;
}

const same = (value: number) => new Intl.NumberFormat().format(value);
const compact = (value: number) =>
  new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);

function tooltip(format: (value: number) => string, xFormat?: (value: string) => string) {
  return (
    <Tooltip
      formatter={(value, name) => [format(Number(value)), name]}
      labelFormatter={(value) => (xFormat ? xFormat(String(value)) : String(value))}
    />
  );
}

/** Bars — compare categories or days; ``stacked`` adds up the series, ``horizontal`` lays them down. */
export function BarsChart({
  data,
  x,
  series,
  stacked = false,
  horizontal = false,
  height = 240,
  format = same,
  xFormat,
  legend = series.length > 1,
}: Common & { data: Datum[]; x: string; series: ChartSeries[]; stacked?: boolean; horizontal?: boolean }) {
  const last = series.length - 1;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: 8, bottom: 0, left: horizontal ? 8 : 0 }}
        barCategoryGap="22%"
      >
        <CartesianGrid vertical={false} horizontal={!horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" tickFormatter={compact} />
            <YAxis type="category" dataKey={x} width={96} {...(xFormat ? { tickFormatter: xFormat } : {})} />
          </>
        ) : (
          <>
            <XAxis dataKey={x} minTickGap={16} {...(xFormat ? { tickFormatter: xFormat } : {})} />
            <YAxis width={44} tickFormatter={compact} />
          </>
        )}
        {tooltip(format, xFormat)}
        {legend ? <Legend /> : null}
        {series.map((s, index) => {
          const top = !stacked || index === last;
          const radius: [number, number, number, number] = horizontal
            ? top
              ? [0, 6, 6, 0]
              : [0, 0, 0, 0]
            : top
              ? [6, 6, 0, 0]
              : [0, 0, 0, 0];
          return (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              {...(stacked ? { stackId: "stack" } : {})}
              fill={s.color ?? paletteColor(index)}
              radius={radius}
              maxBarSize={42}
              isAnimationActive={false}
            />
          );
        })}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Lines — follow values over time; ``area`` fills under them with a soft gradient. */
export function LinesChart({
  data,
  x,
  series,
  area = false,
  curve = "monotone",
  height = 240,
  format = same,
  xFormat,
  legend = series.length > 1,
  children,
}: Common & {
  data: Datum[];
  x: string;
  series: ChartSeries[];
  area?: boolean;
  curve?: "monotone" | "linear" | "step";
  /** marks drawn over the chart (reference lines…) */
  children?: ReactNode;
}) {
  const id = useId().replace(/:/g, "");
  const Chart = area ? AreaChart : LineChart;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Chart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        {area ? (
          <defs>
            {series.map((s, index) => (
              <linearGradient key={s.key} id={`${id}-${index}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color ?? paletteColor(index)} stopOpacity={0.4} />
                <stop offset="100%" stopColor={s.color ?? paletteColor(index)} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
        ) : null}
        <CartesianGrid vertical={false} />
        <XAxis dataKey={x} minTickGap={24} {...(xFormat ? { tickFormatter: xFormat } : {})} />
        <YAxis width={44} tickFormatter={compact} />
        {tooltip(format, xFormat)}
        {legend ? <Legend /> : null}
        {children}
        {series.map((s, index) =>
          area ? (
            <Area
              key={s.key}
              type={curve}
              dataKey={s.key}
              name={s.label}
              stroke={s.color ?? paletteColor(index)}
              strokeWidth={2}
              strokeDasharray={s.dashed ? "6 3" : ""}
              fill={`url(#${id}-${index})`}
              isAnimationActive={false}
            />
          ) : (
            <Line
              key={s.key}
              type={curve}
              dataKey={s.key}
              name={s.label}
              stroke={s.color ?? paletteColor(index)}
              strokeWidth={2.2}
              strokeDasharray={s.dashed ? (DASHES[index % DASHES.length] ?? "") : ""}
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          ),
        )}
      </Chart>
    </ResponsiveContainer>
  );
}

export interface Slice {
  label: string;
  value: number;
  color?: string | undefined;
}

/** A donut — the parts of a whole, the total in its middle and each part named beside it. */
export function DonutChart({
  items,
  total,
  totalLabel,
  height = 220,
  format = same,
}: {
  items: Slice[];
  total?: string | undefined;
  totalLabel?: string | undefined;
  height?: number | undefined;
  format?: ((value: number) => string) | undefined;
}) {
  const sum = items.reduce((all, item) => all + item.value, 0);
  return (
    <div className="ds-donut">
      <div className="ds-donut__ring" style={{ blockSize: height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={items}
              dataKey="value"
              nameKey="label"
              innerRadius="64%"
              outerRadius="92%"
              paddingAngle={items.length > 1 ? 2 : 0}
              cornerRadius={6}
              stroke="none"
              isAnimationActive={false}
            >
              {items.map((item, index) => (
                <Cell key={item.label} fill={item.color ?? paletteColor(index)} />
              ))}
            </Pie>
            <Tooltip formatter={(value, name) => [format(Number(value)), name]} />
          </PieChart>
        </ResponsiveContainer>
        <span className="ds-donut__total">
          <strong>{total ?? format(sum)}</strong>
          {totalLabel ? <small>{totalLabel}</small> : null}
        </span>
      </div>
      <ul className="ds-donut__legend">
        {items.map((item, index) => (
          <li key={item.label}>
            <span className="ds-donut__dot" style={{ background: item.color ?? paletteColor(index) }} />
            <span>{item.label}</span>
            <strong>{format(item.value)}</strong>
            <small>{sum ? Math.round((item.value / sum) * 100) : 0} %</small>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A gauge — how far towards a goal (a level, a quota, a disk), the value in its middle. */
export function GaugeChart({
  value,
  max,
  label,
  color = "var(--color-accent)",
  height = 180,
  format = same,
}: {
  value: number;
  max: number;
  label?: string | undefined;
  color?: string | undefined;
  height?: number | undefined;
  format?: ((value: number) => string) | undefined;
}) {
  const share = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  return (
    <div className="ds-gauge" style={{ blockSize: height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          data={[{ value: share * 100 }]}
          startAngle={210}
          endAngle={-30}
          innerRadius="74%"
          outerRadius="100%"
          barSize={14}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar
            dataKey="value"
            cornerRadius={8}
            fill={color}
            background={{ fill: "color-mix(in srgb, var(--color-text) 8%, transparent)" }}
            isAnimationActive={false}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <span className="ds-gauge__value">
        <strong>{Math.round(share * 100)} %</strong>
        <small>
          {format(value)} / {format(max)}
          {label ? ` · ${label}` : ""}
        </small>
      </span>
    </div>
  );
}

/** A sparkline — a trend at a glance, in a figure's corner or a table's cell. */
export function Sparkline({
  values,
  color = "var(--color-accent)",
  area = true,
  height = 40,
  label,
}: {
  values: number[];
  color?: string | undefined;
  area?: boolean | undefined;
  height?: number | undefined;
  /** what the trend is about, for screen readers */
  label: string;
}) {
  const id = useId().replace(/:/g, "");
  const data = values.map((value, index) => ({ index, value }));
  return (
    <div className="ds-sparkline" role="img" aria-label={label} style={{ blockSize: height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={area ? 0.35 : 0} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill={`url(#${id})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** A heatmap — habits by day and hour (or any two scales), the stronger the deeper; each cell says its value. */
export function HeatmapChart({
  rows,
  columns,
  values,
  label,
  color = "var(--color-accent)",
  format = same,
}: {
  rows: string[];
  columns: string[];
  values: number[][];
  label: string;
  color?: string | undefined;
  format?: ((value: number) => string) | undefined;
}) {
  const max = Math.max(1, ...values.flat());
  return (
    <div className="ds-heatmap">
      {/* the picture for the eyes; the same values as a table for screen readers */}
      <div
        className="ds-heatmap__grid"
        style={{ "--columns": columns.length } as CSSProperties}
        aria-hidden="true"
      >
        <span />
        {columns.map((column) => (
          <span key={column} className="ds-heatmap__head">
            {column}
          </span>
        ))}
        {rows.map((row, r) => (
          <div key={row} className="ds-heatmap__row">
            <span className="ds-heatmap__head">{row}</span>
            {columns.map((column, c) => {
              const value = values[r]?.[c] ?? 0;
              return (
                <span
                  key={column}
                  className="ds-heatmap__cell"
                  title={`${row} · ${column} : ${format(value)}`}
                  style={{
                    background: `color-mix(in srgb, ${color} ${Math.round(8 + (value / max) * 85)}%, transparent)`,
                  }}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="visually-hidden">
        <table>
          <caption>{label}</caption>
          <thead>
            <tr>
              <td />
              {columns.map((column) => (
                <th key={column} scope="col">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, r) => (
              <tr key={row}>
                <th scope="row">{row}</th>
                {columns.map((column, c) => (
                  <td key={column}>{format(values[r]?.[c] ?? 0)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** A radar — a profile over several criteria (tastes by genre, a member against the average). */
export function RadarProfile({
  axes,
  series,
  height = 260,
  format = same,
}: {
  axes: string[];
  series: Array<{ label: string; values: number[]; color?: string | undefined }>;
  height?: number | undefined;
  format?: ((value: number) => string) | undefined;
}) {
  const data = axes.map((axis, index) => ({
    axis,
    ...Object.fromEntries(series.map((s) => [s.label, s.values[index] ?? 0])),
  }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid />
        <PolarAngleAxis dataKey="axis" />
        <Tooltip formatter={(value, name) => [format(Number(value)), name]} />
        {series.length > 1 ? <Legend /> : null}
        {series.map((s, index) => (
          <Radar
            key={s.label}
            dataKey={s.label}
            name={s.label}
            stroke={s.color ?? paletteColor(index)}
            fill={s.color ?? paletteColor(index)}
            fillOpacity={0.22}
            strokeWidth={2}
            isAnimationActive={false}
          />
        ))}
      </RadarChart>
    </ResponsiveContainer>
  );
}
