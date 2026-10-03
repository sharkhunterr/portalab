import { Link } from "react-router";
import { useFormat } from "../../../i18n/format/useFormat";
import type { WidgetProps } from "../widgets/registry";

/**
 * Declarative templates (spec 009 T031; R11): the only way plugin and Marketplace widgets render. Data is
 * rendered as text (never HTML) and links only to in-portal routes.
 */
type Row = Record<string, unknown>;

const text = (value: unknown): string => (value === null || value === undefined ? "" : String(value));
const route = (value: unknown): string | null =>
  typeof value === "string" && value.startsWith("/") && !value.startsWith("//") ? value : null;

function Item({ title, to, meta }: { title: string; to: string | null; meta?: string }) {
  return (
    <li>
      {to ? <Link to={to}>{title}</Link> : title}
      {meta ? <span className="widget__meta"> {meta}</span> : null}
    </li>
  );
}

export function StatTemplate({ payload }: WidgetProps) {
  const format = useFormat();
  const data = (payload.data ?? {}) as Row;
  const value = typeof data.value === "number" ? format.number(data.value) : text(data.value);
  return (
    <p className="widget-stat">
      <span className="widget-stat__value">
        {value}
        {data.unit ? ` ${text(data.unit)}` : ""}
      </span>
      {data.label ? <span className="widget-stat__label">{text(data.label)}</span> : null}
    </p>
  );
}

export function ListTemplate({ payload }: WidgetProps) {
  const items = ((payload.data ?? {}) as Row).items;
  return (
    <ul className="widget-list">
      {(Array.isArray(items) ? (items as Row[]) : []).slice(0, 50).map((item, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: declarative rows have no stable id
        <Item key={index} title={text(item.title)} to={route(item.route)} meta={text(item.meta)} />
      ))}
    </ul>
  );
}

export function TimelineTemplate({ payload }: WidgetProps) {
  const format = useFormat();
  const entries = ((payload.data ?? {}) as Row).entries;
  return (
    <ol className="widget-list">
      {(Array.isArray(entries) ? (entries as Row[]) : []).slice(0, 50).map((entry, index) => (
        <Item
          // biome-ignore lint/suspicious/noArrayIndexKey: declarative rows have no stable id
          key={index}
          title={text(entry.title)}
          to={route(entry.route)}
          meta={typeof entry.at === "string" ? format.dateTime(entry.at) : ""}
        />
      ))}
    </ol>
  );
}

export function ChartTemplate({ payload }: WidgetProps) {
  // an accessible data table first; the visual bars are decorative
  const series = ((payload.data ?? {}) as Row).series;
  const rows = (Array.isArray(series) ? (series as Row[]) : []).slice(0, 5);
  const max = Math.max(
    1,
    ...rows.flatMap((s) =>
      Array.isArray(s.points) ? (s.points as unknown[][]).map((p) => Number(p[1]) || 0) : [],
    ),
  );
  return (
    <table className="widget-chart">
      <tbody>
        {rows.flatMap((s, si) =>
          (Array.isArray(s.points) ? (s.points as unknown[][]) : []).slice(0, 24).map((point, pi) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: positional chart points
            <tr key={`${si}-${pi}`}>
              <th scope="row">
                {text(s.label)} {text(point[0])}
              </th>
              <td>
                <span
                  className="widget-chart__bar"
                  style={{ inlineSize: `${((Number(point[1]) || 0) / max) * 100}%` }}
                />
                {text(point[1])}
              </td>
            </tr>
          )),
        )}
      </tbody>
    </table>
  );
}

export function StatusTemplate({ payload }: WidgetProps) {
  const data = (payload.data ?? {}) as Row;
  const items = Array.isArray(data.items) ? (data.items as Row[]) : [];
  return (
    <ul className="widget-list">
      {items.slice(0, 50).map((item, index) => (
        <Item
          // biome-ignore lint/suspicious/noArrayIndexKey: declarative rows have no stable id
          key={index}
          title={text(item.name)}
          to={route(item.route)}
          meta={text(item.state)}
        />
      ))}
    </ul>
  );
}

export const TEMPLATES = {
  stat: StatTemplate,
  list: ListTemplate,
  chart: ChartTemplate,
  timeline: TimelineTemplate,
  status: StatusTemplate,
} as const;
