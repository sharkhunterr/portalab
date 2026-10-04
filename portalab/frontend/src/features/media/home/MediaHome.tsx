import { useId } from "react";
import { Link } from "react-router";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type ShelfName, useNowPlaying, useShelf } from "../api";
import { MediaGrid } from "../MediaGrid";
import "../media.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/**
 * Media home (spec 024 T024/T028): what is playing, then the discovery shelves. Each shelf loads and fails on
 * its own; an empty shelf names the next action instead of a dead end.
 */
const SHELVES: ShelfName[] = ["continue", "new", "recent", "trending", "recommended"];

function Shelf({ name }: { name: ShelfName }) {
  const t = useT();
  const headingId = useId();
  const shelf = useShelf(name);
  return (
    <section aria-labelledby={headingId} className="media-shelf">
      <h3 id={headingId}>{t(`media:shelf.${name}`)}</h3>
      {shelf.isPending ? <FunctionalState state="loading" /> : null}
      {shelf.isError ? <FunctionalState state="unavailable" onRetry={() => shelf.refetch()} /> : null}
      {shelf.data && shelf.data.items.length === 0 ? (
        <p className="media-muted">
          {shelf.data.next_action === "link_account" ? (
            <Link to="/settings/media-accounts">{t("media:shelf.empty.link_account")}</Link>
          ) : (
            <Link to="/media/browse">{t("media:shelf.empty.browse")}</Link>
          )}
        </p>
      ) : null}
      {shelf.data?.items.length ? (
        <MediaGrid items={shelf.data.items} label={t(`media:shelf.${name}`)} />
      ) : null}
    </section>
  );
}

function NowPlaying() {
  const t = useT();
  const headingId = useId();
  const sessions = useNowPlaying();
  return (
    <section aria-labelledby={headingId} className="media-shelf">
      <h3 id={headingId}>{t("media:home.nowPlaying")}</h3>
      {sessions.data && sessions.data.length === 0 ? (
        <p className="media-muted">{t("media:home.nothingPlaying")}</p>
      ) : null}
      <ul className="media-list">
        {(sessions.data ?? []).map((s) => (
          <li key={s.session}>
            {s.object_id ? (
              <Link to={`/media/${s.object_id}`}>{t(`media:kind.${s.kind}`)}</Link>
            ) : (
              t(`media:kind.${s.kind}`)
            )}{" "}
            · {s.state}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function MediaHome() {
  const t = useT();
  const headingId = useId();
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="film" title={t("media:home.title")} />
      <p>
        <Link to="/media/browse">{t("media:home.browse")}</Link>
      </p>
      <NowPlaying />
      {SHELVES.map((name) => (
        <Shelf key={name} name={name} />
      ))}
    </section>
  );
}

export default MediaHome;
