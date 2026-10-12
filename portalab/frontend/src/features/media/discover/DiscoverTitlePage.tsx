import { useId } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { EnrichedView, metadataImage, normalize } from "../detail/Enrichment";
import { QuotaLine } from "../requests/QuotaSummary";
import { useDiscoverTitle } from "./api";
import { RequestDialog } from "./RequestDialog";
import { StatusBadge } from "./StatusBadge";
import "../media.css";
import "./discover.css";

/**
 * #4: a film or a series before asking for it — its backdrop and poster, synopsis, genres, length and
 * rating, cast and trailer, a series' seasons (which are there or asked for already), where it stands —
 * and « Ask for it » (seasons, 4K, what it takes of my quota). Available, it opens in the library.
 */
export function DiscoverTitlePage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const { kind = "movie", tmdb = "" } = useParams();
  const title = useDiscoverTitle(kind, tmdb);
  if (title.isPending) return <FunctionalState state="loading" />;
  if (title.isError || !title.data) {
    return <FunctionalState state="unavailable" onRetry={() => title.refetch()} />;
  }
  const data = title.data;
  const backdrop = metadataImage(data.backdrop, "w1280");
  const poster = metadataImage(data.poster, "w342");
  const askable =
    !data.request &&
    data.status !== "available" &&
    (data.kind === "movie" ? data.status === "unknown" : data.seasons.some((s) => s.status === "unknown"));
  const facts = [
    data.year ? String(data.year) : null,
    t(`media:kind.${data.kind}`),
    data.runtime ? t("media:discover.minutes", { count: data.runtime }) : null,
    data.rating ? `★ ${format.number(Math.round(data.rating * 10) / 10)}` : null,
  ].filter(Boolean);
  return (
    <article className="discover-title" aria-labelledby={headingId}>
      <header className="discover-title__hero">
        {backdrop ? <img className="discover-title__backdrop" src={backdrop} alt="" /> : null}
        <div className="discover-title__head">
          {poster ? <img className="discover-title__poster" src={poster} alt="" /> : null}
          <div className="discover-title__text">
            <PageHeader
              level={1}
              titleId={headingId}
              title={data.title}
              context={facts.join(" · ")}
              primary={
                data.object_id && data.status === "available" ? (
                  <Link className="ds-button ds-button--primary" to={`/media/${data.object_id}`}>
                    <Icon name="play" size={16} />
                    {t("media:discover.openInLibrary")}
                  </Link>
                ) : askable ? (
                  <RequestDialog
                    target={{
                      tmdb_id: data.tmdb_id,
                      kind: data.kind,
                      title: data.title,
                      ids: data.ids,
                      seasons: data.seasons,
                      four_k: data.four_k,
                    }}
                    trigger={
                      <Button>
                        <Icon name="plus" size={16} />
                        {t("media:discover.ask")}
                      </Button>
                    }
                  />
                ) : null
              }
              secondary={
                data.trailer ? (
                  <a
                    className="ds-button ds-button--secondary"
                    href={`https://www.youtube.com/watch?v=${encodeURIComponent(data.trailer)}`}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    <Icon name="play" size={16} />
                    {t("media:discover.trailer")}
                  </a>
                ) : undefined
              }
            />
            <p className="discover-title__state">
              <StatusBadge item={data} />
              {data.object_id && data.status !== "available" ? (
                <Link to={`/media/${data.object_id}`}>{t("media:discover.seeJourney")}</Link>
              ) : null}
            </p>
            {askable ? <QuotaLine kind={data.kind} /> : null}
          </div>
        </div>
      </header>
      {/* the same rich details as a library title: facts, cast and crew, the saga, money, production */}
      <EnrichedView data={normalize({ ...data.metadata, title: data.title })} />
      {data.seasons.length ? (
        <section className="media-enriched discover-title__seasons" aria-label={t("media:discover.seasons")}>
          <div className="media-enriched__block">
            <h3>{t("media:discover.seasons")}</h3>
            <ul className="discover-seasons">
              {data.seasons.map((season) => (
                <li key={season.number}>
                  <strong>{season.name ?? t("media:discover.season", { number: season.number })}</strong>
                  <span className="media-muted">
                    {[
                      season.episodes ? t("media:discover.episodes", { count: season.episodes }) : null,
                      season.air_date ? season.air_date.slice(0, 4) : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                  <StatusBadge item={{ status: season.status, request: null }} />
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </article>
  );
}

export default DiscoverTitlePage;
