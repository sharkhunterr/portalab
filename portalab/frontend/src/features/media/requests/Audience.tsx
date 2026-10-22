import { Link } from "react-router";
import { AdminEmpty } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import type { RequestInsights } from "./api";

type Leader = NonNullable<RequestInsights["leaders"]>["requests"][number];

/** issue 222: how many other members watched my requests — a number, never who. */
export function AudienceSummary({ data }: { data: NonNullable<RequestInsights["audience"]> }) {
  const t = useT();
  const format = useFormat();
  const { viewers, plays, seen, requested } = data;
  return (
    <div className="requests-cards">
      <div className="requests-card">
        <span className="requests-card__label">{t("media:myRequests.audience.viewers")}</span>
        <span className="requests-card__value" data-tone="ok">
          {format.number(viewers)}
        </span>
        <span className="admin-muted">{t("media:myRequests.audience.viewersHint", { count: viewers })}</span>
      </div>
      <div className="requests-card">
        <span className="requests-card__label">{t("media:myRequests.audience.plays")}</span>
        <span className="requests-card__value">{format.number(plays)}</span>
        <span className="admin-muted">{t("media:myRequests.audience.seen", { seen, count: requested })}</span>
        <span className="requests-meter">
          <span style={{ inlineSize: `${requested ? Math.round((seen / requested) * 100) : 0}%` }} />
        </span>
      </div>
    </div>
  );
}

/** issue 222 (sold): my requests by how many members watched them, and my rank by audience. */
export function AudienceTitles({ data }: { data: NonNullable<RequestInsights["audience_titles"]> }) {
  const t = useT();
  if (!data.items.length) return <AdminEmpty icon="users" title={t("media:myRequests.audience.none")} />;
  return (
    <>
      <p className="requests-audience__rank">
        <Icon name="trophy" size={16} />
        {data.position
          ? t("media:myRequests.audience.rank", { position: data.position, total: data.total })
          : t("media:myRequests.audience.rankNone", { total: data.total })}
      </p>
      <ol className="insights-posters">
        {data.items.map((work, index) => (
          <li key={work.id ?? work.title} className="insights-poster">
            <Link to={work.route ?? (work.id ? `/media/${work.id}` : "/media/requests")}>
              <span className="insights-poster__art">
                {work.image_id ? (
                  <img src={`/api/v1/media/images/${work.image_id}`} alt="" loading="lazy" />
                ) : (
                  <Icon name="film" size={28} />
                )}
                <span className="insights-poster__rank">{index + 1}</span>
              </span>
              <span className="insights-poster__title">{work.title}</span>
              <span className="insights-poster__meta">
                {t("media:myRequests.audience.viewersCount", { count: work.viewers })} ·{" "}
                {t("media:insights.plays", { count: work.plays })}
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </>
  );
}

const BOARDS = ["requests", "viewers", "per_request"] as const;

/** issue 222 (sold): the requesters' podiums — named as on the leaderboards, else an anonymous member. */
export function Leaders({ data }: { data: NonNullable<RequestInsights["leaders"]> }) {
  const t = useT();
  const format = useFormat();
  const who = (entry: Leader) =>
    entry.me ? t("media:myRequests.leaders.you") : (entry.name ?? t("media:myRequests.leaders.someone"));
  return (
    <div className="requests-leaders">
      {BOARDS.map((board) => (
        <section key={board} className="requests-leaders__board" aria-labelledby={`leaders-${board}`}>
          <h3 id={`leaders-${board}`}>{t(`media:myRequests.leaders.${board}`)}</h3>
          <p className="admin-muted">{t(`media:myRequests.leaders.${board}Hint`)}</p>
          {data[board].length ? (
            <ol>
              {data[board].map((entry, index) => (
                <li
                  // biome-ignore lint/suspicious/noArrayIndexKey: a podium of the server's order, anonymous members alike
                  key={index}
                  data-rank={entry.rank <= 3 ? entry.rank : undefined}
                  data-me={entry.me || undefined}
                >
                  <span className="requests-leaders__rank">{entry.rank}</span>
                  <span className="requests-leaders__name">{who(entry)}</span>
                  <strong>
                    {format.number(board === "per_request" ? Math.round(entry.value * 10) / 10 : entry.value)}
                  </strong>
                </li>
              ))}
            </ol>
          ) : (
            <p className="admin-muted">{t("media:myRequests.leaders.empty")}</p>
          )}
        </section>
      ))}
    </div>
  );
}
