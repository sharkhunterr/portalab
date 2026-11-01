import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { type CSSProperties, useRef, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { MentionChip, type SourceItem } from "../../news/ExternalNews";
import { sourceIcon } from "../../news/sourceKind";
import { Poster } from "../MediaGrid";
import type { FeedItem, Follow } from "./api";
import { FollowedMark } from "./FollowedMark";

/** issue 299: the theme's chart palette (as « My progression »'s sources): the server's arrivals keep the media
 * colour, each news source one of the others — a second round lightened; the name always beside it. */
const SERVER = "var(--chart-3)";
const PAGE = 20; // the news on a page (the library's arrivals among them, at their dates)
const PALETTE = [1, 2, 4, 5, 7, 8, 9, 10].map((n) => `var(--chart-${n})`);

interface Source {
  key: string;
  label: string;
  icon: string;
  color: string;
}

interface Entry {
  key: string;
  at: string;
  source: Source;
  forMe: boolean;
  unread: boolean;
  arrival?: FeedItem;
  news?: SourceItem;
}

function colorOf(index: number): string {
  const base = PALETTE[index % PALETTE.length] as string;
  return index < PALETTE.length ? base : `color-mix(in oklab, ${base} 60%, white)`;
}

export function SourceBadge({ source }: { source: Source }) {
  return (
    <span className="feed-badge" style={{ "--badge": source.color } as CSSProperties}>
      <Icon name={source.icon} size={12} />
      {source.label}
    </span>
  );
}

function ArrivalEntry({ entry }: { entry: Entry }) {
  const t = useT();
  const item = entry.arrival as FeedItem;
  return (
    <Link to={`/media/${item.object_id}`} className="feed-entry__body">
      <Poster src={item.image_id ? `/api/v1/media/images/${item.image_id}` : null} kind={item.kind} />
      <span className="feed-entry__text">
        <strong className="feed-entry__title">
          {item.title}
          {item.year ? ` (${item.year})` : ""}
        </strong>
        <span className="feed-entry__summary">
          {item.units?.length
            ? t("media:feed.units", { count: item.units.length, list: item.units.slice(-4).join(", ") })
            : t(`media:feed.arrived.${item.kind}`)}
        </span>
        <span className="feed-entry__chips">
          {item.because.map((b) => (
            <span key={`${b.kind}:${b.label}`} className="feed-chip" data-followed="true">
              <Icon name={b.kind === "person" ? "user" : b.kind === "title" ? "tv" : "tag"} size={12} />
              {b.label}
              <FollowedMark />
            </span>
          ))}
        </span>
      </span>
    </Link>
  );
}

function NewsEntry({ entry }: { entry: Entry }) {
  const t = useT();
  const item = entry.news as SourceItem;
  return (
    <div className="feed-entry__body">
      <span className="feed-entry__picture" aria-hidden="true">
        {item.picture ? (
          <img src={item.picture} alt="" loading="lazy" />
        ) : (
          <Icon name="newspaper" size={26} />
        )}
      </span>
      <span className="feed-entry__text">
        <a href={item.link} target="_blank" rel="noopener noreferrer" className="feed-entry__title">
          {item.title}
          <Icon name="external" size={12} />
          <span className="visually-hidden">{t("news:external.opensSite")}</span>
        </a>
        {item.summary ? <span className="feed-entry__summary">{item.summary}</span> : null}
        {item.mentions?.length ? (
          <span className="feed-entry__chips">
            {item.mentions.slice(0, 4).map((m) => (
              <MentionChip key={`${m.kind}:${m.ref}`} mention={m} />
            ))}
          </span>
        ) : null}
      </span>
    </div>
  );
}

/** The pages of the stream: the first, the last, the current one and its neighbours, gaps marked. */
function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (page: number) => void }) {
  const t = useT();
  if (pages <= 1) return null;
  const wanted = [...new Set([0, page - 1, page, page + 1, pages - 1])].filter((n) => n >= 0 && n < pages);
  // a gap is written as the page after it, negated (its key)
  const shown: number[] = [];
  for (const n of wanted.sort((a, b) => a - b)) {
    const before = shown[shown.length - 1];
    if (before !== undefined && n - before > 1) shown.push(-n);
    shown.push(n);
  }
  return (
    <nav className="feed-pager" aria-label={t("media:feed.pages")}>
      <button
        type="button"
        className="ds-button ds-button--ghost"
        disabled={page === 0}
        onClick={() => onPage(page - 1)}
        aria-label={t("media:feed.previous")}
      >
        <Icon name="chevron-left" size={16} />
      </button>
      {shown.map((n) =>
        n < 0 ? (
          <span key={n} className="feed-pager__gap" aria-hidden="true">
            …
          </span>
        ) : (
          <button
            key={n}
            type="button"
            className="ds-button ds-button--ghost"
            aria-current={n === page ? "page" : undefined}
            aria-label={t("media:feed.page", { page: n + 1 })}
            onClick={() => onPage(n)}
          >
            {n + 1}
          </button>
        ),
      )}
      <button
        type="button"
        className="ds-button ds-button--ghost"
        disabled={page >= pages - 1}
        onClick={() => onPage(page + 1)}
        aria-label={t("media:feed.next")}
      >
        <Icon name="chevron-right" size={16} />
      </button>
    </nav>
  );
}

type Asked = { source?: string[]; title?: string[]; person?: string[] };

async function timeline(query: Asked & { offset?: number; limit: number }) {
  const { data } = await api.GET("/api/v1/me/news/timeline", { params: { query } });
  return data ?? { items: [], total: 0, sources: [] };
}

/**
 * « Mon fil » (issue 299) as one stream: what the library brought for what I follow and what every source
 * published — the editors' and mine —, newest first, day by day, each with its source's coloured badge
 * (and its kind's icon: a YouTube channel, a podcast…); a page at a time, filtered to what is for me, or
 * to one source. What came after I last read it is marked new.
 */
export function Timeline({
  arrivals,
  follows,
  seenAt,
}: {
  arrivals: FeedItem[];
  follows: Follow[];
  seenAt: string | null | undefined;
}) {
  const t = useT();
  const format = useFormat();
  const top = useRef<HTMLElement>(null);
  const [only, setOnly] = useState<string>("all");
  const [page, setPage] = useState(0);
  const people = follows.filter((f) => f.kind === "person").map((f) => f.ref);
  const titles = follows.filter((f) => f.kind === "title").map((f) => f.ref);
  const server = only === "server";
  const forMe = only === "mine";
  const picked = only !== "all" && !server && !forMe ? only : null;
  const asked: Asked = picked ? { source: [picked] } : forMe ? { title: titles, person: people } : {};
  // from the second page on, the previous page's last item too: where this page's dates begin
  const offset = page === 0 ? 0 : page * PAGE - 1;
  const news = useQuery({
    queryKey: ["news", "timeline", asked, page],
    enabled: !server && !(forMe && !titles.length && !people.length),
    placeholderData: keepPreviousData,
    queryFn: () => timeline({ ...asked, offset, limit: page === 0 ? PAGE : PAGE + 1 }),
  });
  // every source I read — each its filter, even one quiet lately
  const listed = useQuery({
    queryKey: ["news", "timeline", "sources"],
    queryFn: async () => (await timeline({ limit: 1 })).sources,
  });
  const rows = news.isEnabled ? (news.data?.items ?? []) : [];
  const boundary = page > 0 ? rows[0] : undefined;
  const items = page > 0 ? rows.slice(1) : rows;
  const total = news.isEnabled ? (news.data?.total ?? 0) : 0;
  const pages = server ? Math.ceil(arrivals.length / PAGE) : Math.max(1, Math.ceil(total / PAGE));
  // cheap: the page's few entries, built again at each render
  const { entries, sources } = (() => {
    const followedPeople = new Set(people);
    const followedTitles = new Set(titles);
    const since = seenAt ? Date.parse(seenAt) : null;
    const bySource = new Map<string, Source>(
      (listed.data ?? []).map((source, index) => [
        source.id,
        { key: source.id, label: source.name, icon: sourceIcon(source.kind), color: colorOf(index) },
      ]),
    );
    const known: Source = { key: "server", label: t("media:feed.server"), icon: "server", color: SERVER };
    // the library's arrivals among this page's news, at their dates (all of them, a page each, alone)
    const last = page >= pages - 1;
    const upper = boundary ? Date.parse(boundary.published_at) : Number.POSITIVE_INFINITY;
    const end = items[items.length - 1];
    const lower = last || !end ? Number.NEGATIVE_INFINITY : Date.parse(end.published_at);
    const brought = server
      ? arrivals.slice(page * PAGE, (page + 1) * PAGE)
      : picked
        ? []
        : arrivals.filter((a) => Date.parse(a.at) < upper && Date.parse(a.at) >= lower);
    const out: Entry[] = brought.map((item) => ({
      key: `a:${item.object_id}`,
      at: item.at,
      source: known,
      forMe: true,
      unread: Boolean(item.unread),
      arrival: item,
    }));
    for (const item of items) {
      out.push({
        key: `n:${item.id}`,
        at: item.published_at,
        source: bySource.get(item.source_id) ?? {
          key: item.source_id,
          label: item.source,
          icon: sourceIcon(item.source_kind),
          color: colorOf(bySource.size),
        },
        forMe: (item.mentions ?? []).some(
          (m) =>
            (m.kind === "person" && followedPeople.has(m.ref)) ||
            (m.kind === "title" && followedTitles.has(m.ref)),
        ),
        unread: since !== null && Date.parse(item.published_at) > since,
        news: item,
      });
    }
    out.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
    return { entries: out, sources: [known, ...bySource.values()] };
  })();
  const choose = (next: string) => {
    setOnly(next);
    setPage(0);
  };
  const turn = (next: number) => {
    setPage(next);
    top.current?.scrollIntoView({ block: "start" });
  };
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86_400_000).toDateString();
  const dayOf = (at: string) => {
    const day = new Date(at).toDateString();
    return day === today
      ? t("media:feed.today")
      : day === yesterday
        ? t("media:feed.yesterday")
        : format.date(at, "long");
  };
  let last = "";
  return (
    <section className="feed-section" aria-labelledby="feed-stream" ref={top}>
      <h2 id="feed-stream" className="visually-hidden">
        {t("media:feed.title")}
      </h2>
      <fieldset className="feed-filters">
        <legend className="visually-hidden">{t("media:feed.filter")}</legend>
        <button type="button" aria-pressed={only === "all"} onClick={() => choose("all")}>
          {t("media:feed.all")}
        </button>
        <button type="button" aria-pressed={forMe} onClick={() => choose("mine")}>
          <Icon name="sparkles" size={14} />
          {t("media:feed.forMe")}
        </button>
        {sources.map((source) => (
          <button
            key={source.key}
            type="button"
            aria-pressed={only === source.key}
            onClick={() => choose(only === source.key ? "all" : source.key)}
            style={{ "--badge": source.color } as CSSProperties}
            className="feed-filters__source"
          >
            <span className="feed-filters__dot" aria-hidden="true" />
            <Icon name={source.icon} size={14} />
            {source.label}
          </button>
        ))}
      </fieldset>
      {entries.length ? (
        <ol className="feed-stream" aria-busy={news.isPlaceholderData || undefined}>
          {entries.map((entry) => {
            const day = dayOf(entry.at);
            const header = day !== last ? day : null;
            last = day;
            return (
              <li
                key={entry.key}
                className="feed-entry"
                data-unread={entry.unread || undefined}
                data-for-me={entry.forMe || undefined}
              >
                {header ? <h3 className="feed-stream__day">{header}</h3> : null}
                <div className="feed-entry__card" style={{ "--badge": entry.source.color } as CSSProperties}>
                  <span className="feed-entry__meta">
                    <SourceBadge source={entry.source} />
                    {entry.unread ? <span className="feed-item__new">{t("media:feed.new")}</span> : null}
                    {entry.forMe && entry.news ? (
                      <span className="feed-entry__forme">{t("media:feed.forMe")}</span>
                    ) : null}
                    <span className="feed-entry__when">
                      {format.relative((Date.parse(entry.at) - Date.now()) / 1000)}
                    </span>
                  </span>
                  {entry.arrival ? <ArrivalEntry entry={entry} /> : <NewsEntry entry={entry} />}
                </div>
              </li>
            );
          })}
        </ol>
      ) : news.isFetching ? null : (
        <p className="admin-muted">{t("media:feed.nothingYet")}</p>
      )}
      <Pager page={page} pages={pages} onPage={turn} />
    </section>
  );
}
