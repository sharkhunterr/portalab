import { useEffect, useId, useState } from "react";
import { Link } from "react-router";
import { SelectField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { MySources, SourceSuggestions } from "../../news/MySources";
import { personPath, useCatalogFacets } from "../api";
import { metadataImage } from "../detail/Enrichment";
import { Poster } from "../MediaGrid";
import {
  type FeedUpcoming,
  type Follow,
  type FollowKind,
  useFeed,
  useFollows,
  useFollowToggle,
  useMarkSeen,
} from "./api";
import { Timeline } from "./Timeline";
import "./feed.css";

const KIND_ICONS: Record<FollowKind, string> = { person: "user", title: "tv", genre: "tag" };

/** Where a followed subject lives: a person's page, a series', or the library by genre. */
function followRoute(follow: Follow): string {
  if (follow.kind === "person") return personPath(follow.label);
  if (follow.kind === "title") return `/media/${follow.ref}`;
  return `/media/browse?genre=${encodeURIComponent(follow.ref)}`;
}

function Coming({ credit }: { credit: FeedUpcoming }) {
  const t = useT();
  const body = (
    <>
      <Poster
        src={metadataImage(credit.poster, "w185")}
        kind={credit.kind === "tv" ? "series" : credit.kind}
      />
      <span className="feed-item__text">
        <span className="feed-item__head">
          <span className="feed-item__when">{credit.year}</span>
          <span className="feed-item__status">{t(`media:feed.status.${credit.status}`)}</span>
        </span>
        <strong className="feed-item__title">{credit.title}</strong>
        <span className="feed-item__because">
          <span className="feed-chip">
            <Icon name="user" size={12} />
            {credit.person}
          </span>
        </span>
      </span>
    </>
  );
  return (
    <li className="feed-item">
      {credit.route ? (
        <Link to={credit.route} className="feed-item__link">
          {body}
        </Link>
      ) : (
        <span className="feed-item__link">{body}</span>
      )}
    </li>
  );
}

/** What I follow — each to stop following, the genres to add from the library's. */
function Follows({ follows }: { follows: Follow[] }) {
  const t = useT();
  const toggle = useFollowToggle();
  const facets = useCatalogFacets(undefined);
  const [genre, setGenre] = useState("");
  const followed = new Set(follows.filter((f) => f.kind === "genre").map((f) => f.ref));
  const genres = (facets.data?.genres ?? []).filter((g) => !followed.has(g));
  return (
    <section className="feed-section" aria-labelledby="feed-follows">
      <h2 id="feed-follows">
        <Icon name="settings" size={18} /> {t("media:feed.follows", { count: follows.length })}
      </h2>
      {follows.length ? <p className="admin-muted">{t("media:feed.howTo")}</p> : null}
      {(["person", "title", "genre"] as const).map((kind) => {
        const mine = follows.filter((f) => f.kind === kind);
        return mine.length ? (
          <div key={kind} className="feed-follows">
            <h3>{t(`media:feed.kinds.${kind}`)}</h3>
            <ul>
              {mine.map((follow) => (
                <li key={follow.ref} className="feed-chip feed-chip--follow">
                  <Link to={followRoute(follow)}>
                    <Icon name={KIND_ICONS[kind]} size={14} />
                    {follow.label}
                  </Link>
                  <button
                    type="button"
                    aria-label={t("media:feed.unfollow", { name: follow.label })}
                    disabled={toggle.isPending}
                    onClick={() => toggle.mutate({ kind, ref: follow.ref, on: false })}
                  >
                    <Icon name="close" size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null;
      })}
      {genres.length ? (
        <form
          className="feed-add"
          onSubmit={(event) => {
            event.preventDefault();
            if (genre)
              toggle.mutate({ kind: "genre", ref: genre, on: true }, { onSuccess: () => setGenre("") });
          }}
        >
          <SelectField
            label={t("media:feed.addGenre")}
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
          >
            <option value="">{t("media:feed.chooseGenre")}</option>
            {genres.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </SelectField>
          <button
            type="submit"
            className="ds-button ds-button--secondary"
            disabled={!genre || toggle.isPending}
          >
            <Icon name="plus" size={16} />
            {t("media:follow.follow")}
          </button>
        </form>
      ) : null}
    </section>
  );
}

/**
 * « Mon fil » (issue 299): what the library brought lately for the people, series and genres I follow — each with
 * why, the unread marked —, what is announced for the people I follow, and what I follow. Opening it reads it.
 */
export default function FeedPage() {
  const t = useT();
  const headingId = useId();
  const feed = useFeed();
  const follows = useFollows();
  const seen = useMarkSeen();
  const loaded = feed.isSuccess;
  // biome-ignore lint/correctness/useExhaustiveDependencies: once per visit, when the feed is shown
  useEffect(() => {
    if (loaded) seen.mutate();
  }, [loaded]);
  const items = feed.data?.items ?? [];
  const upcoming = feed.data?.upcoming ?? [];
  const mine = follows.data ?? [];
  return (
    <section aria-labelledby={headingId} className="ds-stack feed-page">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="rss"
        title={t("media:feed.title")}
        context={t("media:feed.intro")}
      />
      {feed.isPending ? <FunctionalState state="loading" /> : null}
      {feed.isError ? <FunctionalState state="error" onRetry={() => feed.refetch()} /> : null}
      {loaded && !mine.length && !items.length ? (
        <EmptyState
          icon="rss"
          title={t("media:feed.empty")}
          message={t("media:feed.howTo")}
          action={{ label: t("media:feed.toLibrary"), href: "/media" }}
        />
      ) : null}
      {upcoming.length ? (
        <section className="feed-section" aria-labelledby="feed-upcoming">
          <h2 id="feed-upcoming">
            <Icon name="calendar" size={18} /> {t("media:feed.upcoming")}
          </h2>
          <ul className="feed-list feed-list--rail">
            {upcoming.map((credit) => (
              <Coming key={`${credit.kind}:${credit.tmdb_id}`} credit={credit} />
            ))}
          </ul>
        </section>
      ) : null}
      {/* issue 349: the administrator's suggested sources, one click each */}
      <SourceSuggestions />
      {/* issue 299: one stream — the library's arrivals and every source's news, each with its source's colour */}
      {loaded ? <Timeline arrivals={items} follows={mine} seenAt={feed.data?.seen_at} /> : null}
      <details className="feed-manage">
        <summary>
          <Icon name="settings" size={16} /> {t("media:feed.manage")}
        </summary>
        {follows.isSuccess ? <Follows follows={mine} /> : null}
        {/* issue 299: my own sources, read for me alone */}
        <MySources items={false} />
      </details>
    </section>
  );
}
