import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMeasures } from "../insights/api";
import type { RequestInsights } from "./api";

type Depth = NonNullable<RequestInsights["audience_depth"]>;

/**
 * The audience in depth (issue 222, sold): how fast another member watched what I asked for once it
 * arrived, my requests against everyone's, films against series, the genres of the requests the members
 * watch (mine and the whole server's), the long tail and the plays over time.
 */
export function AudienceDepth({ data }: { data: Depth }) {
  const t = useT();
  const format = useFormat();
  const measures = useMeasures();
  const span = (hours: number) => measures.duration(Math.max(60, hours * 3600));
  const { reactivity, versus, kinds, genres } = data;
  const percent = (value: number | null) => (value === null ? "—" : format.percent(value));
  const ratio = (value: number | null) => (value === null ? "—" : format.number(value));
  const label = (iso: string) =>
    data.over_time.unit === "month"
      ? new Date(iso).toLocaleDateString(undefined, { month: "short", year: "2-digit" })
      : format.date(iso, "short");
  return (
    <div className="requests-depth">
      <section aria-labelledby="depth-reactivity">
        <h3 id="depth-reactivity">{t("media:myRequests.depth.reactivity")}</h3>
        <p className="admin-muted">{t("media:myRequests.depth.reactivityHint")}</p>
        <div className="requests-cards requests-cards--row">
          <div className="requests-card">
            <span className="requests-card__label">{t("media:myRequests.depth.median")}</span>
            <span className="requests-card__value">
              {reactivity.median_hours === null ? "—" : span(reactivity.median_hours)}
            </span>
            <span className="admin-muted">
              {t("media:myRequests.depth.waiting", { count: reactivity.waiting })}
            </span>
          </div>
          {reactivity.fastest[0] ? (
            <div className="requests-card">
              <span className="requests-card__label">{t("media:myRequests.depth.fastest")}</span>
              <span className="requests-card__value" data-tone="ok">
                {span(reactivity.fastest[0].hours)}
              </span>
              <span className="admin-muted">{reactivity.fastest[0].title}</span>
            </div>
          ) : null}
          {reactivity.slowest[0] ? (
            <div className="requests-card">
              <span className="requests-card__label">{t("media:myRequests.depth.slowest")}</span>
              <span className="requests-card__value">{span(reactivity.slowest[0].hours)}</span>
              <span className="admin-muted">{reactivity.slowest[0].title}</span>
            </div>
          ) : null}
        </div>
        {reactivity.buckets.some((b) => b.count) ? (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart
              data={reactivity.buckets.map((b) => ({ ...b, label: t(`media:myRequests.bucket.${b.key}`) }))}
            >
              <XAxis dataKey="label" fontSize={12} />
              <YAxis allowDecimals={false} fontSize={12} width={28} />
              <Tooltip />
              <Bar
                dataKey="count"
                name={t("media:myRequests.depth.firstViews")}
                fill="var(--color-accent)"
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        ) : null}
      </section>

      <section aria-labelledby="depth-versus">
        <h3 id="depth-versus">{t("media:myRequests.depth.versus")}</h3>
        <p className="admin-muted">{t("media:myRequests.depth.versusHint")}</p>
        <Compare
          label={t("media:myRequests.depth.seenRate")}
          mine={versus.mine.seen_rate}
          server={versus.server.seen_rate}
          show={percent}
        />
        <Compare
          label={t("media:myRequests.depth.perRequest")}
          mine={versus.mine.viewers_per_request}
          server={versus.server.viewers_per_request}
          show={ratio}
        />
        <div className="requests-cards requests-cards--row">
          <div className="requests-card">
            <span className="requests-card__label">{t("media:myRequests.depth.lateShare")}</span>
            <span className="requests-card__value">{percent(data.late_share)}</span>
            <span className="admin-muted">{t("media:myRequests.depth.lateShareHint")}</span>
          </div>
          {(["movie", "series"] as const).map((kind) => (
            <Kind key={kind} kind={kind} rates={kinds[kind]} percent={percent} ratio={ratio} />
          ))}
        </div>
      </section>

      <section aria-labelledby="depth-genres">
        <h3 id="depth-genres">{t("media:myRequests.depth.genres")}</h3>
        <p className="admin-muted">{t("media:myRequests.depth.genresHint")}</p>
        <div className="requests-depth__genres">
          {(["mine", "server"] as const).map((whose) => (
            <figure key={whose}>
              <figcaption>{t(`media:myRequests.depth.genres_${whose}`)}</figcaption>
              {genres[whose].length ? (
                <ol>
                  {genres[whose].map((genre) => (
                    <li key={genre.name}>
                      <span>{genre.name}</span>
                      <span className="requests-meter">
                        <span
                          style={{
                            inlineSize: `${Math.round((genre.viewers / (genres[whose][0]?.viewers || 1)) * 100)}%`,
                          }}
                        />
                      </span>
                      <strong>{t("media:myRequests.audience.viewersCount", { count: genre.viewers })}</strong>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="admin-muted">{t("media:myRequests.leaders.empty")}</p>
              )}
            </figure>
          ))}
        </div>
      </section>

      {data.over_time.points.length ? (
        <section aria-labelledby="depth-time">
          <h3 id="depth-time">{t("media:myRequests.depth.overTime")}</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={data.over_time.points}>
              <XAxis dataKey="date" tickFormatter={label} fontSize={12} minTickGap={16} />
              <YAxis allowDecimals={false} fontSize={12} width={28} />
              <Tooltip labelFormatter={(v) => label(String(v))} />
              <Bar
                dataKey="plays"
                name={t("media:myRequests.audience.plays")}
                fill="var(--color-accent-alt)"
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </section>
      ) : null}
    </div>
  );
}

function Compare({
  label,
  mine,
  server,
  show,
}: {
  label: string;
  mine: number | null;
  server: number | null;
  show: (value: number | null) => string;
}) {
  const t = useT();
  const top = Math.max(mine ?? 0, server ?? 0) || 1;
  return (
    <div className="requests-compare">
      <span className="requests-card__label">{label}</span>
      {(
        [
          ["mine", mine],
          ["server", server],
        ] as const
      ).map(([whose, value]) => (
        <div key={whose} className="requests-compare__row" data-whose={whose}>
          <span>{t(`media:myRequests.depth.${whose}`)}</span>
          <span className="requests-meter">
            <span style={{ inlineSize: `${Math.round(((value ?? 0) / top) * 100)}%` }} />
          </span>
          <strong>{show(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function Kind({
  kind,
  rates,
  percent,
  ratio,
}: {
  kind: "movie" | "series";
  rates: Depth["kinds"]["movie"];
  percent: (value: number | null) => string;
  ratio: (value: number | null) => string;
}) {
  const t = useT();
  return (
    <div className="requests-card">
      <span className="requests-card__label">
        {t(`media:insights.categories.${kind === "movie" ? "movies" : "series"}`)}
      </span>
      <span className="requests-card__value">{ratio(rates.viewers_per_request)}</span>
      <span className="admin-muted">
        {t("media:myRequests.depth.kindLine", { rate: percent(rates.seen_rate), count: rates.available })}
      </span>
    </div>
  );
}
