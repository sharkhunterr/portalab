import type { CSSProperties, ReactNode } from "react";
import { Funnel, FunnelChart, LabelList, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { fades, paletteColor, type Slice, useFocus } from "./Charts";
import "./charts.css";

/**
 * The chart kit's drawn shapes (issue 117) — in the spirit of Telemetra's: plain SVG, intensity told by
 * depth of colour, light concentric tracks, a soft entrance (none under reduced motion). Each one names its
 * values in text too (a label, a title, a hidden list), never by colour alone.
 */
const same = (value: number) => new Intl.NumberFormat().format(value);

function wedge(cx: number, cy: number, inner: number, outer: number, start: number, end: number): string {
  const p = (r: number, a: number) => `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  const large = end - start > Math.PI ? 1 : 0;
  return `M${p(inner, start)}L${p(outer, start)}A${outer},${outer} 0 ${large},1 ${p(outer, end)}L${p(inner, end)}A${inner},${inner} 0 ${large},0 ${p(inner, start)}Z`;
}

/** Issue 125: a legend entry that singles its part out (the others fade); again, all come back. */
function Pick({
  name,
  active,
  pick,
  children,
}: {
  name: string;
  active: string | null;
  pick: (key: string) => void;
  children: ReactNode;
}) {
  return (
    <button type="button" className="ds-chart-pick" aria-pressed={active === name} onClick={() => pick(name)}>
      {children}
    </button>
  );
}

const dim = (active: string | null, name: string): CSSProperties | undefined =>
  fades(active, name) ? { opacity: 0.15 } : undefined;

/** A polar wheel — when things happen: 24 hours as a clock, 7 days around a week; deeper means more. */
export function PolarWheel({
  values,
  labels,
  label,
  color = "var(--color-accent)",
  size = 220,
  format = same,
  every = 1,
}: {
  values: number[];
  labels: string[];
  label: string;
  color?: string | undefined;
  size?: number | undefined;
  format?: ((value: number) => string) | undefined;
  /** name one slot out of ``every`` (3 for the hours of a clock) */
  every?: number | undefined;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const inner = size * 0.17;
  const outer = size * 0.38;
  const max = Math.max(1, ...values);
  const slot = (2 * Math.PI) / Math.max(1, values.length);
  const gap = values.length > 12 ? 0.05 : 0.1;
  return (
    <figure className="ds-polar" aria-label={label}>
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
        {[0.33, 0.67, 1].map((r) => (
          <circle key={r} cx={cx} cy={cy} r={inner + (outer - inner) * r} className="ds-track" />
        ))}
        {values.map((value, i) => {
          const share = value / max;
          const start = i * slot - Math.PI / 2 + gap / 2;
          const end = (i + 1) * slot - Math.PI / 2 - gap / 2;
          const reach = inner + (outer - inner) * Math.max(share, 0.05);
          const middle = (start + end) / 2;
          const at = outer + size * 0.07;
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: slots are positional (hours, days)
            <g key={i} className="ds-chart-pop" style={{ "--i": i } as CSSProperties}>
              <path
                d={wedge(cx, cy, inner, reach, start, end)}
                fill={color}
                fillOpacity={0.14 + share * 0.82}
              >
                <title>{`${labels[i] ?? i} : ${format(value)}`}</title>
              </path>
              {i % every === 0 ? (
                <text
                  x={cx + at * Math.cos(middle)}
                  y={cy + at * Math.sin(middle)}
                  className="ds-polar__label"
                  data-strong={share === 1 || undefined}
                >
                  {labels[i]}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

/** Concentric rings — several shares side by side (completion by kind, goals reached), each on its track. */
export function RingsChart({
  items,
  size = 220,
}: {
  items: Array<{ label: string; value: number; max?: number; color?: string }>;
  size?: number | undefined;
}) {
  const cx = size / 2;
  const width = Math.min(16, (size * 0.36) / Math.max(1, items.length) - 4);
  const [active, pick] = useFocus();
  return (
    <div className="ds-rings">
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={items.map((i) => i.label).join(", ")}>
        {items.map((item, index) => {
          const r = size * 0.44 - index * (width + 5);
          const share = Math.min(1, item.value / (item.max ?? 100));
          const circumference = 2 * Math.PI * r;
          const color = item.color ?? paletteColor(index);
          return (
            <g key={item.label} transform={`rotate(-90 ${cx} ${cx})`} style={dim(active, item.label)}>
              <circle cx={cx} cy={cx} r={r} className="ds-ring__track" strokeWidth={width} />
              <circle
                cx={cx}
                cy={cx}
                r={r}
                fill="none"
                stroke={color}
                strokeWidth={width}
                strokeLinecap="round"
                strokeDasharray={`${circumference * share} ${circumference}`}
                className="ds-ring__value"
              />
            </g>
          );
        })}
      </svg>
      <ul className="ds-chart-legend">
        {items.map((item, index) => (
          <li key={item.label} data-faded={fades(active, item.label) || undefined}>
            <Pick name={item.label} active={active} pick={pick}>
              <span
                className="ds-chart-legend__dot"
                style={{ background: item.color ?? paletteColor(index) }}
              />
              {item.label}
            </Pick>
            <strong>{Math.round((item.value / (item.max ?? 100)) * 100)} %</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A stacked progress bar — a whole split into its parts, lying or standing, each part named. */
export function StackedProgress({
  items,
  total,
  vertical = false,
  label,
  format = same,
}: {
  items: Slice[];
  /** the bar's full length (what is not filled stays as the track); the parts' sum by default */
  total?: number | undefined;
  vertical?: boolean | undefined;
  label: string;
  format?: ((value: number) => string) | undefined;
}) {
  const sum = items.reduce((all, item) => all + item.value, 0);
  const whole = Math.max(total ?? sum, 1);
  const [active, pick] = useFocus();
  return (
    <div className="ds-stacked" data-vertical={vertical || undefined}>
      <div className="ds-stacked__bar" role="img" aria-label={label}>
        {items.map((item, index) => (
          <span
            key={item.label}
            className="ds-stacked__part"
            title={`${item.label} : ${format(item.value)}`}
            style={{
              [vertical ? "blockSize" : "inlineSize"]: `${(item.value / whole) * 100}%`,
              background: item.color ?? paletteColor(index),
              ...dim(active, item.label),
            }}
          />
        ))}
      </div>
      <ul className="ds-chart-legend">
        {items.map((item, index) => (
          <li key={item.label} data-faded={fades(active, item.label) || undefined}>
            <Pick name={item.label} active={active} pick={pick}>
              <span
                className="ds-chart-legend__dot"
                style={{ background: item.color ?? paletteColor(index) }}
              />
              {item.label}
            </Pick>
            <strong>{format(item.value)}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Stacked progress bars standing side by side — the same split for several groups (members, months). */
export function StackedColumns({
  groups,
  label,
  format = same,
  height = 180,
}: {
  groups: Array<{ label: string; items: Slice[] }>;
  label: string;
  format?: ((value: number) => string) | undefined;
  height?: number | undefined;
}) {
  const max = Math.max(1, ...groups.map((g) => g.items.reduce((a, i) => a + i.value, 0)));
  const names = groups[0]?.items.map((i) => i.label) ?? [];
  const [active, pick] = useFocus();
  return (
    <div className="ds-columns">
      <div className="ds-columns__plot" role="img" aria-label={label} style={{ blockSize: height }}>
        {groups.map((group) => (
          <div key={group.label} className="ds-columns__group">
            <div className="ds-columns__bar">
              {group.items.map((item, index) => (
                <span
                  key={item.label}
                  title={`${group.label} · ${item.label} : ${format(item.value)}`}
                  style={{
                    blockSize: `${(item.value / max) * 100}%`,
                    background: item.color ?? paletteColor(index),
                    ...dim(active, item.label),
                  }}
                />
              ))}
            </div>
            <span className="ds-columns__label">{group.label}</span>
          </div>
        ))}
      </div>
      <ul className="ds-chart-legend">
        {names.map((name, index) => (
          <li key={name} data-faded={fades(active, name) || undefined}>
            <Pick name={name} active={active} pick={pick}>
              <span className="ds-chart-legend__dot" style={{ background: paletteColor(index) }} />
              {name}
            </Pick>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A waffle — a share as a hundred squares: easy to read even for those who do not like percentages. */
export function WaffleChart({
  value,
  label,
  color = "var(--color-accent)",
}: {
  value: number;
  label: string;
  color?: string | undefined;
}) {
  const filled = Math.round(Math.min(100, Math.max(0, value)));
  return (
    <figure className="ds-waffle">
      <figcaption>
        <strong>{filled} %</strong> {label}
      </figcaption>
      <div className="ds-waffle__grid" role="img" aria-label={`${label} : ${filled} %`}>
        {Array.from({ length: 100 }, (_, i) => (
          <span
            // biome-ignore lint/suspicious/noArrayIndexKey: a hundred identical squares
            key={i}
            data-on={i >= 100 - filled || undefined}
            style={i >= 100 - filled ? { background: color } : undefined}
          />
        ))}
      </div>
    </figure>
  );
}

/** Mirror bars — two sides of the same scale face to face (a pyramid): men and women, me and the others. */
export function MirrorBars({
  rows,
  left,
  right,
  format = same,
}: {
  rows: Array<{ label: string; left: number; right: number }>;
  left: { label: string; color?: string };
  right: { label: string; color?: string };
  format?: ((value: number) => string) | undefined;
}) {
  const max = Math.max(1, ...rows.flatMap((r) => [r.left, r.right]));
  return (
    <div className="ds-mirror">
      <div className="ds-mirror__head">
        <span>{left.label}</span>
        <span />
        <span>{right.label}</span>
      </div>
      {rows.map((row) => (
        <div key={row.label} className="ds-mirror__row">
          <span className="ds-mirror__side" data-side="left">
            <small>{format(row.left)}</small>
            <span
              style={{ inlineSize: `${(row.left / max) * 100}%`, background: left.color ?? paletteColor(0) }}
            />
          </span>
          <span className="ds-mirror__label">{row.label}</span>
          <span className="ds-mirror__side" data-side="right">
            <span
              style={{
                inlineSize: `${(row.right / max) * 100}%`,
                background: right.color ?? paletteColor(1),
              }}
            />
            <small>{format(row.right)}</small>
          </span>
        </div>
      ))}
    </div>
  );
}

/** Before → after — how each value moved between two periods, the arrow saying which way. */
export function DumbbellChart({
  rows,
  before,
  after,
  format = same,
}: {
  rows: Array<{ label: string; before: number; after: number }>;
  before: string;
  after: string;
  format?: ((value: number) => string) | undefined;
}) {
  const max = Math.max(1, ...rows.flatMap((r) => [r.before, r.after]));
  const at = (v: number) => `${(v / max) * 100}%`;
  return (
    <div className="ds-dumbbell">
      <ul className="ds-chart-legend">
        <li>
          <span className="ds-chart-legend__dot ds-dumbbell__before" />
          {before}
        </li>
        <li>
          <span className="ds-chart-legend__dot" style={{ background: "var(--color-accent)" }} />
          {after}
        </li>
      </ul>
      {rows.map((row) => {
        const up = row.after >= row.before;
        return (
          <div key={row.label} className="ds-dumbbell__row">
            <span className="ds-dumbbell__label">{row.label}</span>
            <span className="ds-dumbbell__track">
              <span
                className="ds-dumbbell__line"
                data-up={up || undefined}
                style={{
                  insetInlineStart: at(Math.min(row.before, row.after)),
                  inlineSize: `calc(${at(Math.abs(row.after - row.before))})`,
                }}
              />
              <span
                className="ds-dumbbell__dot ds-dumbbell__before"
                style={{ insetInlineStart: at(row.before) }}
              />
              <span className="ds-dumbbell__dot" style={{ insetInlineStart: at(row.after) }} />
            </span>
            <span className="ds-dumbbell__value" data-up={up || undefined}>
              {format(row.before)} → <strong>{format(row.after)}</strong>
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Lollipops — a ranking without heavy bars: a thin stem and a dot at the value. */
export function LollipopChart({
  rows,
  format = same,
  color = "var(--color-accent)",
}: {
  rows: Array<{ label: string; value: number }>;
  format?: ((value: number) => string) | undefined;
  color?: string | undefined;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ol className="ds-lollipop">
      {rows.map((row) => (
        <li key={row.label}>
          <span className="ds-lollipop__label">{row.label}</span>
          <span className="ds-lollipop__track">
            <span
              className="ds-lollipop__stem"
              style={{ inlineSize: `${(row.value / max) * 100}%`, background: color }}
            >
              <span className="ds-lollipop__dot" style={{ background: color }} />
            </span>
          </span>
          <strong>{format(row.value)}</strong>
        </li>
      ))}
    </ol>
  );
}

/** A funnel — how many go from one step to the next (requested → available → watched). */
export function FunnelSteps({
  steps,
  height = 240,
  format = same,
}: {
  steps: Slice[];
  height?: number | undefined;
  format?: ((value: number) => string) | undefined;
}) {
  const data = steps.map((step, index) => ({ ...step, fill: step.color ?? paletteColor(index) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <FunnelChart>
        <Tooltip formatter={(value, name) => [format(Number(value)), name]} />
        <Funnel dataKey="value" nameKey="label" data={data} isAnimationActive={false} stroke="none">
          <LabelList position="center" dataKey="label" className="ds-funnel__label" />
        </Funnel>
      </FunnelChart>
    </ResponsiveContainer>
  );
}

/** A sunburst — a whole, its parts and their own parts, ring after ring (kinds, then genres). */
export function SunburstChart({
  groups,
  height = 260,
  format = same,
}: {
  groups: Array<{ label: string; color?: string; children: Array<{ label: string; value: number }> }>;
  height?: number | undefined;
  format?: ((value: number) => string) | undefined;
}) {
  const inner = groups.map((g, index) => ({
    label: g.label,
    value: g.children.reduce((a, c) => a + c.value, 0),
    fill: g.color ?? paletteColor(index),
  }));
  const outer = groups.flatMap((g, index) =>
    g.children.map((c, k) => ({
      label: `${g.label} · ${c.label}`,
      value: c.value,
      fill: `color-mix(in srgb, ${g.color ?? paletteColor(index)} ${90 - k * 15}%, var(--color-surface))`,
    })),
  );
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Tooltip formatter={(value, name) => [format(Number(value)), name]} />
        <Pie
          data={inner}
          dataKey="value"
          nameKey="label"
          innerRadius="22%"
          outerRadius="52%"
          stroke="var(--color-surface)"
          strokeWidth={2}
          isAnimationActive={false}
        />
        <Pie
          data={outer}
          dataKey="value"
          nameKey="label"
          innerRadius="55%"
          outerRadius="88%"
          stroke="var(--color-surface)"
          strokeWidth={2}
          paddingAngle={1}
          isAnimationActive={false}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
