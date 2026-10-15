import { type CSSProperties, type ReactNode, useId, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  BarStack,
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
 * words or offers the table beside it. Issue 125: a click on a legend entry singles that series out (the
 * others fade), a second click brings them all back.
 */
export const PALETTE = Array.from({ length: 10 }, (_, index) => `var(--chart-${index + 1})`);
const DASHES = ["", "6 3", "2 3", "8 3 2 3"];

/** Issue 125: ten hues, then the same lighter, then darker — thirty series told apart before one repeats. */
export function paletteColor(index: number): string {
  const base = PALETTE[index % PALETTE.length] ?? "var(--color-accent)";
  const tier = Math.floor(index / PALETTE.length) % 3;
  if (tier === 1) return `color-mix(in oklab, ${base} 58%, white)`;
  if (tier === 2) return `color-mix(in oklab, ${base} 62%, black)`;
  return base;
}

/** Issue 125: the series a legend click singled out, and the click itself (again: all come back). */
export function useFocus(): [string | null, (key: string) => void] {
  const [active, setActive] = useState<string | null>(null);
  return [active, (key) => setActive((current) => (current === key ? null : key))];
}

const FADED = 0.15;
/** Whether a series fades behind the one singled out. */
export const fades = (active: string | null, key: string) => active !== null && active !== key;

/** A legend whose entries single a series out (rendered in place: the chart finds its ``Legend``). */
function focusLegend(active: string | null, pick: (key: string) => void) {
  return (
    <Legend
      onClick={(entry) => {
        const key = (entry as { dataKey?: unknown }).dataKey;
        if (key !== undefined && key !== null) pick(String(key));
      }}
      formatter={(value, entry) => (
        <span
          className="ds-chart-pick"
          data-faded={fades(active, String((entry as { dataKey?: unknown }).dataKey)) || undefined}
        >
          {value}
        </span>
      )}
    />
  );
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
  /** a number of pixels, or ``"100%"`` to fill a widget's block */
  height?: number | "100%" | undefined;
  /** issue 117: a widget's small chart keeps the room — no Y axis, no X axis, no grid as asked */
  xAxis?: boolean | undefined;
  yAxis?: boolean | undefined;
  grid?: boolean | undefined;
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
  xAxis = true,
  yAxis = true,
  grid = true,
}: Common & { data: Datum[]; x: string; series: ChartSeries[]; stacked?: boolean; horizontal?: boolean }) {
  const [active, pick] = useFocus();
  const round: [number, number, number, number] = horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0];
  const bars = series.map((s, index) => (
    <Bar
      key={s.key}
      dataKey={s.key}
      name={s.label}
      fill={s.color ?? paletteColor(index)}
      fillOpacity={fades(active, s.key) ? FADED : 1}
      radius={stacked ? 0 : round}
      maxBarSize={42}
      isAnimationActive={false}
    />
  ));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: 8, bottom: 0, left: horizontal ? 8 : 0 }}
        barCategoryGap="22%"
      >
        {grid ? <CartesianGrid vertical={false} horizontal={!horizontal} /> : null}
        {horizontal ? (
          <>
            <XAxis type="number" tickFormatter={compact} hide={!xAxis} />
            <YAxis
              type="category"
              dataKey={x}
              width={96}
              hide={!yAxis}
              {...(xFormat ? { tickFormatter: xFormat } : {})}
            />
          </>
        ) : (
          <>
            <XAxis
              dataKey={x}
              minTickGap={16}
              hide={!xAxis}
              {...(xFormat ? { tickFormatter: xFormat } : {})}
            />
            <YAxis width={44} tickFormatter={compact} hide={!yAxis} />
          </>
        )}
        {tooltip(format, xFormat)}
        {legend ? focusLegend(active, pick) : null}
        {stacked ? (
          // issue 125: the whole stack's end is round, however thin its last part
          <BarStack radius={round}>{bars}</BarStack>
        ) : (
          bars
        )}
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
  xAxis = true,
  yAxis = true,
  grid = true,
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
  const [active, pick] = useFocus();
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
        {grid ? <CartesianGrid vertical={false} /> : null}
        <XAxis dataKey={x} minTickGap={24} hide={!xAxis} {...(xFormat ? { tickFormatter: xFormat } : {})} />
        <YAxis width={44} tickFormatter={compact} hide={!yAxis} />
        {tooltip(format, xFormat)}
        {legend ? focusLegend(active, pick) : null}
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
              strokeOpacity={fades(active, s.key) ? FADED : 1}
              fillOpacity={fades(active, s.key) ? FADED : 1}
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
              strokeWidth={active === s.key ? 3 : 2.2}
              strokeOpacity={fades(active, s.key) ? FADED : 1}
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
  height?: number | "100%" | undefined;
  format?: ((value: number) => string) | undefined;
}) {
  const sum = items.reduce((all, item) => all + item.value, 0);
  const [active, pick] = useFocus();
  return (
    <div className="ds-donut">
      <div
        className="ds-donut__ring"
        style={{ blockSize: height, minBlockSize: height === "100%" ? 120 : undefined }}
      >
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
                <Cell
                  key={item.label}
                  fill={item.color ?? paletteColor(index)}
                  fillOpacity={fades(active, item.label) ? FADED : 1}
                />
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
          <li key={item.label} data-faded={fades(active, item.label) || undefined}>
            <button
              type="button"
              className="ds-chart-pick"
              aria-pressed={active === item.label}
              onClick={() => pick(item.label)}
            >
              <span className="ds-donut__dot" style={{ background: item.color ?? paletteColor(index) }} />
              <span>{item.label}</span>
            </button>
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
  const [active, pick] = useFocus();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid />
        <PolarAngleAxis dataKey="axis" />
        <Tooltip formatter={(value, name) => [format(Number(value)), name]} />
        {series.length > 1 ? focusLegend(active, pick) : null}
        {series.map((s, index) => (
          <Radar
            key={s.label}
            dataKey={s.label}
            name={s.label}
            stroke={s.color ?? paletteColor(index)}
            fill={s.color ?? paletteColor(index)}
            fillOpacity={fades(active, s.label) ? 0.04 : 0.22}
            strokeOpacity={fades(active, s.label) ? FADED : 1}
            strokeWidth={2}
            isAnimationActive={false}
          />
        ))}
      </RadarChart>
    </ResponsiveContainer>
  );
}
