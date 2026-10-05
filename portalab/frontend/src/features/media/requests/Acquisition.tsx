import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { AdminEmpty } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import { useMeasures } from "../insights/api";
import type { Acquisition } from "./api";

/**
 * Time to availability (027): how long my requests took to arrive — median, fastest and slowest; the
 * delays in buckets; each request placed by when I asked compared with the release (before it, its first
 * month, its first year, an older title) against how long it took; the median per moment.
 */
const MOMENTS = ["before", "month", "year", "catalog"] as const;
const TOOLTIP = { background: "var(--color-surface-raised)", border: "1px solid var(--color-border)" };

export function AcquisitionView({ data }: { data: Acquisition }) {
  const t = useT();
  const measures = useMeasures();
  const span = (hours: number) => measures.duration(Math.max(60, hours * 3600));
  const total = data.buckets.reduce((sum, b) => sum + b.count, 0);
  if (!total) return <AdminEmpty icon="clock" title={t("media:myRequests.acquisitionNone")} />;
  const points = data.points
    .filter((p) => p.asked_after_days !== null)
    .map((p) => ({
      ...p,
      x: Math.max(-400, Math.min(3650, p.asked_after_days ?? 0)),
      y: Math.max(0.05, p.hours),
    }));
  const took = t("media:myRequests.took");
  return (
    <div className="requests-acquisition">
      <div className="requests-cards requests-cards--row">
        <div className="requests-card">
          <span className="requests-card__label">{t("media:myRequests.median")}</span>
          <span className="requests-card__value">
            {data.median_hours !== null ? span(data.median_hours) : "—"}
          </span>
          <span className="admin-muted">{t("media:myRequests.waiting", { count: data.pending })}</span>
        </div>
        {data.fastest[0] ? (
          <div className="requests-card">
            <span className="requests-card__label">{t("media:myRequests.fastest")}</span>
            <span className="requests-card__value" data-tone="ok">
              {span(data.fastest[0].hours)}
            </span>
            <span className="admin-muted">{data.fastest[0].title}</span>
          </div>
        ) : null}
        {data.slowest[0] ? (
          <div className="requests-card">
            <span className="requests-card__label">{t("media:myRequests.slowest")}</span>
            <span className="requests-card__value">{span(data.slowest[0].hours)}</span>
            <span className="admin-muted">{data.slowest[0].title}</span>
          </div>
        ) : null}
      </div>
      <div className="requests-acquisition__charts">
        <figure>
          <figcaption>{t("media:myRequests.delays")}</figcaption>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart
              data={data.buckets.map((b) => ({ ...b, label: t(`media:myRequests.bucket.${b.key}`) }))}
            >
              <XAxis dataKey="label" stroke="var(--color-text-muted)" fontSize={12} />
              <YAxis allowDecimals={false} stroke="var(--color-text-muted)" fontSize={12} width={28} />
              <Tooltip contentStyle={TOOLTIP} />
              <Bar
                dataKey="count"
                name={t("media:myRequests.stat.total")}
                fill="var(--color-accent)"
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </figure>
        {points.length ? (
          <figure>
            <figcaption>{t("media:myRequests.scatter")}</figcaption>
            <ResponsiveContainer width="100%" height={200}>
              <ScatterChart margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name={t("media:myRequests.askedAfter")}
                  stroke="var(--color-text-muted)"
                  fontSize={12}
                  tickFormatter={(v) => t("media:myRequests.days", { count: Number(v) })}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  scale="log"
                  domain={[0.05, "auto"]}
                  name={took}
                  stroke="var(--color-text-muted)"
                  fontSize={12}
                  width={56}
                  tickFormatter={(v) => span(Number(v))}
                />
                <ZAxis range={[44, 44]} />
                <Tooltip
                  contentStyle={TOOLTIP}
                  formatter={(value, name) =>
                    name === took ? span(Number(value)) : t("media:myRequests.days", { count: Number(value) })
                  }
                />
                {MOMENTS.map((moment) => (
                  <Scatter
                    key={moment}
                    name={t(`media:myRequests.moment.${moment}`)}
                    data={points.filter((p) => p.moment === moment)}
                    fill={`var(--moment-${moment})`}
                    isAnimationActive={false}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </figure>
        ) : null}
      </div>
      <ul className="requests-moments">
        {data.moments.map((m) => (
          <li key={m.moment} data-moment={m.moment}>
            <span className="requests-swatch" />
            <span>{t(`media:myRequests.moment.${m.moment}`)}</span>
            <span className="admin-muted">{t("media:myRequests.requests", { count: m.count })}</span>
            <strong>{m.median_hours !== null ? span(m.median_hours) : "—"}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
