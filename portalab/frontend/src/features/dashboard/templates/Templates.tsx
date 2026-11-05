import { Link } from "react-router";
import { StatusBadge, type Tone } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { PosterTickets } from "../../support/tickets/MediaTickets";
import type { WidgetProps } from "../widgets/registry";

/**
 * Declarative templates (spec 009 T031; R11): the only way plugin and Marketplace widgets render. Data is
 * rendered as text (never HTML) and links only to in-portal routes.
 */
type Row = Record<string, unknown>;

const text = (value: unknown): string => (value === null || value === undefined ? "" : String(value));
const route = (value: unknown): string | null =>
  typeof value === "string" && value.startsWith("/") && !value.startsWith("//") ? value : null;

/** Known states → a tone and a shared label (027): badges instead of raw words. */
const TONES: Record<string, Tone> = {
  open: "info",
  new: "info",
  pending: "info",
  waiting: "info",
  scheduled: "info",
  approved: "info",
  processing: "info",
  in_progress: "info",
  investigating: "warn",
  identified: "warn",
  monitoring: "info",
  active: "warn",
  playing: "ok",
  paused: "neutral",
  resolved: "ok",
  closed: "neutral",
  available: "ok",
  ended: "neutral",
  declined: "bad",
  failed: "bad",
  cancelled: "neutral",
  critical: "bad",
  major: "warn",
  minor: "info",
};
const ISO_DATE = /^\d{4}-\d{2}-\d{2}(T[\d:.]+(Z|[+-]\d{2}:?\d{2})?)?$/;

function useStateLabel() {
  const t = useT();
  return (state: string) => {
    const key = `dashboard:state.${state}`;
    const label = t(key);
    return label === key.split(":")[1] ? state.replace(/_/g, " ") : label;
  };
}

/** A meta text: an ISO date becomes a readable (relative when close) date; anything else stays as is. */
function useMeta() {
  const format = useFormat();
  return (value: unknown): string => {
    const raw = text(value);
    if (!ISO_DATE.test(raw)) return raw;
    const at = new Date(raw);
    const seconds = (at.getTime() - Date.now()) / 1000;
    if (Math.abs(seconds) < 6 * 86400 && raw.includes("T")) return format.relative(seconds);
    return raw.includes("T") ? format.dateTime(at) : format.date(at);
  };
}

function Thumb({ item, icon }: { item: Row; icon: string | null | undefined }) {
  const image = typeof item.image_id === "string" ? `/api/v1/media/images/${item.image_id}` : null;
  if (image) {
    return (
      <span className="widget-row__thumb widget-row__thumb--poster">
        <img src={image} alt="" loading="lazy" />
        {/* issue 354: a library title's open reports */}
        <PosterTickets
          mediaId={typeof item.route === "string" ? /^\/media\/([0-9a-f-]{36})$/.exec(item.route)?.[1] : null}
        />
      </span>
    );
  }
  const name = typeof item.icon === "string" ? item.icon : icon;
  return name ? (
    <span className="widget-row__thumb" aria-hidden="true">
      <Icon name={name} size={18} />
    </span>
  ) : null;
}

/** #48: « not read yet » — a dot, said in words for screen readers. */
export function UnreadDot() {
  const t = useT();
  return (
    <span
      className="widget-unread__dot"
      role="img"
      aria-label={t("dashboard:unreadOne")}
      title={t("dashboard:unreadOne")}
    />
  );
}

function Row({ item, icon }: { item: Row; icon: string | null | undefined }) {
  const meta = useMeta();
  const stateLabel = useStateLabel();
  const to = route(item.route);
  const state = typeof item.state === "string" ? item.state : null;
  const progress = typeof item.progress === "number" ? Math.min(1, Math.max(0, item.progress)) : null;
  const details = [item.subtitle, item.meta, item.at].map(meta).filter(Boolean).join(" · ");
  const body = (
    <>
      <Thumb item={item} icon={icon} />
      <span className="widget-row__main">
        <span className="widget-row__title">
          {item.unread === true ? <UnreadDot /> : null}
          {text(item.title)}
        </span>
        {details ? <span className="widget-row__meta">{details}</span> : null}
        {progress !== null ? (
          <span className="widget-row__progress" aria-hidden="true">
            <span style={{ inlineSize: `${Math.round(progress * 100)}%` }} />
          </span>
        ) : null}
      </span>
      {state ? <StatusBadge tone={TONES[state] ?? "neutral"}>{stateLabel(state)}</StatusBadge> : null}
      {to ? <Icon name="chevron-right" size={16} className="widget-row__chevron" /> : null}
    </>
  );
  return (
    <li className="widget-row" data-unread={item.unread === true || undefined}>
      {to ? <Link to={to}>{body}</Link> : <span>{body}</span>}
    </li>
  );
}

export function StatTemplate({ payload, icon }: WidgetProps) {
  const format = useFormat();
  const data = (payload.data ?? {}) as Row;
  const value = typeof data.value === "number" ? format.number(data.value) : text(data.value);
  return (
    <p className="widget-stat">
      {icon ? (
        <span className="widget-stat__icon" aria-hidden="true">
          <Icon name={icon} size={22} />
        </span>
      ) : null}
      <span className="widget-stat__value">
        {value}
        {data.unit ? <span className="widget-stat__unit"> {text(data.unit)}</span> : null}
      </span>
      {data.label ? <span className="widget-stat__label">{text(data.label)}</span> : null}
    </p>
  );
}

export function ListTemplate({ payload, icon }: WidgetProps) {
  const items = ((payload.data ?? {}) as Row).items;
  return (
    <ul className="widget-rows">
      {(Array.isArray(items) ? (items as Row[]) : []).slice(0, 50).map((item, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: declarative rows have no stable id
        <Row key={index} item={item} icon={icon} />
      ))}
    </ul>
  );
}

export function TimelineTemplate({ payload, icon }: WidgetProps) {
  const entries = ((payload.data ?? {}) as Row).entries;
  return (
    <ol className="widget-rows widget-rows--timeline">
      {(Array.isArray(entries) ? (entries as Row[]) : []).slice(0, 50).map((entry, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: declarative rows have no stable id
        <Row key={index} item={entry} icon={icon} />
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

export function StatusTemplate({ payload, icon }: WidgetProps) {
  const data = (payload.data ?? {}) as Row;
  const items = Array.isArray(data.items) ? (data.items as Row[]) : [];
  return (
    <ul className="widget-rows">
      {items.slice(0, 50).map((item, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: declarative rows have no stable id
        <Row key={index} item={{ ...item, title: item.title ?? item.name }} icon={icon} />
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
