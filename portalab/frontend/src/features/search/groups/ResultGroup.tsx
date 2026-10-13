import { useId, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { personPath } from "../../media/api";
import { metadataImage } from "../../media/detail/Enrichment";
import { PosterBadge } from "../../media/discover/StatusBadge";
import { Poster } from "../../media/MediaGrid";
import { type GroupOut, type ItemOut, kindKey, runSearch, type SearchParams } from "../api";
import { badgesOf, mediaGroup, ResultBadges, rolesOf, SourceIcon } from "../presentation";

/**
 * One result group (spec 008 T017): its own functional state (an unavailable source never hides the
 * others), highlighted snippets rendered as text (``<mark>`` from structured segments — never HTML from
 * the server) and "more results" paging within the group.
 */
export function Snippet({ item }: { item: ItemOut }) {
  if (!item.snippet.length) return null;
  return (
    <p className="search-result__snippet">
      {item.snippet.map((segment, index) =>
        // biome-ignore lint/suspicious/noArrayIndexKey: segments are positional and never reordered
        segment.hit ? <mark key={index}>{segment.text}</mark> : <span key={index}>{segment.text}</span>,
      )}
    </p>
  );
}

/** A result of a source other than media: its source's icon, title, badges and snippet. */
function Result({ item }: { item: ItemOut }) {
  const t = useT();
  return (
    <li className="search-result">
      <span className="search-result__icon" aria-hidden="true">
        <SourceIcon kind={item.kind} />
      </span>
      <div className="search-result__body">
        <Link to={item.url_ref} className="search-result__title">
          {item.title}
        </Link>
        {item.matched_by === "semantic" ? (
          <span className="search-result__badge">{t("search:mode.semantic")}</span>
        ) : null}
        <ResultBadges badges={badgesOf(t, item)} />
        <Snippet item={item} />
      </div>
    </li>
  );
}

/** #67: a title as a poster card — its poster (or its kind's icon), title, state and genres. */
function PosterResult({ item }: { item: ItemOut }) {
  const t = useT();
  const image = item.facets?.image;
  // the type is the section's own heading; the standing is on the poster, as everywhere (#92)
  const status = item.facets?.status;
  const badges = badgesOf(t, item)
    .slice(1)
    .filter((badge) => !status || badge.label !== badgesOf(t, { kind: "", facets: { status } })[0]?.label);
  // #4: a title to ask for carries TMDB's poster
  const src = image
    ? `/api/v1/media/images/${image}`
    : item.kind === "request"
      ? metadataImage(item.facets?.poster, "w185")
      : null;
  return (
    <li className="search-poster">
      <Link to={item.url_ref} className="search-poster__link">
        <span className="media-card__frame search-poster__frame">
          <Poster src={src} kind={item.facets?.type ?? "movie"} />
          <PosterBadge status={status} />
        </span>
        <span className="search-poster__title">{item.title}</span>
      </Link>
      <ResultBadges badges={badges} />
      {item.facets?.person ? (
        // #92: whom the query found — « by Robin Hobb », « with Chris O'Dowd » — and their page
        <Link className="search-poster__credit" to={personPath(item.facets.person)}>
          {t(`search:credit.${item.facets.role ?? "credit"}`, { name: item.facets.person })}
        </Link>
      ) : null}
      {item.facets?.genres ? <span className="search-poster__meta">{item.facets.genres}</span> : null}
    </li>
  );
}

/** #92: a person — their portrait (or an icon), name, roles and how many titles — opening their page. */
function PersonResult({ item }: { item: ItemOut }) {
  const t = useT();
  const portrait = metadataImage(item.facets?.portrait, "w185");
  return (
    <li className="search-person">
      <Link to={item.url_ref} className="search-person__link">
        <span className="search-person__portrait" aria-hidden="true">
          {portrait ? <img src={portrait} alt="" loading="lazy" /> : <Icon name="user" size={30} />}
        </span>
        <span className="search-person__name">{item.title}</span>
      </Link>
      <span className="search-poster__meta">{rolesOf(t, item)}</span>
    </li>
  );
}

/** #67: media results split by type (films, series, books…); the other sources stay one list. */
function sectionsOf(kind: string, items: ItemOut[]) {
  if (kind !== "media") return [{ key: "all", label: "", icon: "", items }];
  const sections = new Map<string, { key: string; label: string; icon: string; items: ItemOut[] }>();
  for (const item of items) {
    const by = mediaGroup(item.facets?.type) ?? {
      key: "media:other",
      label: "search:mediaKind.other",
      icon: "film",
    };
    const section = sections.get(by.key) ?? { ...by, items: [] };
    section.items.push(item);
    sections.set(by.key, section);
  }
  // films, series, games, books… — always in the same order on the page
  const rank = (key: string) => {
    const at = MEDIA_ORDER.indexOf(key.replace("media:", ""));
    return at < 0 ? MEDIA_ORDER.length : at;
  };
  return [...sections.values()].sort((a, b) => rank(a.key) - rank(b.key));
}

const MEDIA_ORDER = [
  "movie",
  "series",
  "game",
  "book",
  "audiobook",
  "album",
  "live",
  "season",
  "episode",
  "track",
];

export function ResultGroup({ group, params }: { group: GroupOut; params: SearchParams }) {
  const t = useT();
  const headingId = useId();
  const [extra, setExtra] = useState<ItemOut[]>([]);
  const [cursor, setCursor] = useState<string | null>(group.next_cursor);
  const [loading, setLoading] = useState(false);
  const items = [...group.items, ...extra];
  async function more() {
    setLoading(true);
    try {
      const page = await runSearch({ ...params, kinds: [group.kind] }, cursor);
      const next = page.groups.find((g) => g.kind === group.kind);
      setExtra((current) => [...current, ...(next?.items ?? [])]);
      setCursor(next?.next_cursor ?? null);
    } finally {
      setLoading(false);
    }
  }
  return (
    <section aria-labelledby={headingId} className="search-group" data-kind={group.kind}>
      <h3 id={headingId} className="search-group__head">
        <span className="search-group__icon" aria-hidden="true">
          <SourceIcon kind={group.kind} />
        </span>
        {t(kindKey(group.label_key))} <span className="search-group__count">{items.length}</span>
      </h3>
      {group.state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("search:groupUnavailable")} />
      ) : (
        <div className="search-group__sections">
          {sectionsOf(group.kind, items).map((section) => (
            <div key={section.key} className="search-group__section">
              {section.label ? (
                <h4 className="search-group__subhead">
                  <Icon name={section.icon} size={14} /> {t(section.label)}{" "}
                  <span className="search-group__count">{section.items.length}</span>
                </h4>
              ) : null}
              {group.kind === "person" ? (
                <ul className="search-people">
                  {section.items.map((item) => (
                    <PersonResult key={`${item.kind}:${item.id}`} item={item} />
                  ))}
                </ul>
              ) : group.kind === "media" || group.kind === "request" ? (
                <ul className="search-posters">
                  {section.items.map((item) => (
                    <PosterResult key={`${item.kind}:${item.id}`} item={item} />
                  ))}
                </ul>
              ) : (
                <ul className="search-group__items">
                  {section.items.map((item) => (
                    <Result key={`${item.kind}:${item.id}`} item={item} />
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
      {cursor && group.state !== "unavailable" ? (
        <Button variant="secondary" onClick={more} disabled={loading} aria-busy={loading || undefined}>
          {t("search:more")}
        </Button>
      ) : null}
    </section>
  );
}
