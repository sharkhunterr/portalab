import { useQuery } from "@tanstack/react-query";
import { type CSSProperties, useMemo, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type SourceItem, useSourceItems } from "../../news/ExternalNews";
import { Poster } from "../MediaGrid";
import type { FeedItem, Follow } from "./api";

/** #299: the theme's chart palette (as « My progression »'s sources): the server's arrivals keep the media
 * colour, each news source one of the others — a second round lightened; the name always beside it. */
const SERVER = "var(--chart-3)";
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
            <span key={`${b.kind}:${b.label}`} className="feed-chip">
              <Icon name={b.kind === "person" ? "user" : b.kind === "title" ? "tv" : "tag"} size={12} />
              {b.label}
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
              <Link key={`${m.kind}:${m.ref}`} to={m.route} className="feed-chip">
                <Icon name={m.kind === "person" ? "user" : "film"} size={12} />
                {m.label}
              </Link>
            ))}
          </span>
        ) : null}
      </span>
    </div>
  );
}

/**
 * « Mon fil » (#299) as one stream: what the library brought for what I follow and what every source
 * published — the editors' and mine —, newest first, day by day, each with its source's coloured badge;
 * filtered to what is for me, or to one source. What came after I last read it is marked new.
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
  const [only, setOnly] = useState<string>("all");
  const mine = useQuery({
    queryKey: ["news", "sources", "mine", "items", 100],
    queryFn: async () =>
      (await api.GET("/api/v1/me/news/sources/items", { params: { query: { limit: 100 } } })).data?.items ??
      [],
  });
  const editorial = useSourceItems({}, 60);
  const { entries, sources } = useMemo(() => {
    const people = new Set(follows.filter((f) => f.kind === "person").map((f) => f.ref));
    const titles = new Set(follows.filter((f) => f.kind === "title").map((f) => f.ref));
    const since = seenAt ? Date.parse(seenAt) : null;
    const news = new Map<string, SourceItem>();
    for (const item of [...(Array.isArray(mine.data) ? mine.data : []), ...(editorial.data ?? [])]) {
      news.set(item.id, item);
    }
    const names = [...new Map([...news.values()].map((i) => [i.source_id, i.source])).entries()].sort(
      (a, b) => a[1].localeCompare(b[1]),
    );
    const bySource = new Map<string, Source>(
      names.map(([id, label], index) => [id, { key: id, label, icon: "rss", color: colorOf(index) }]),
    );
    const server: Source = { key: "server", label: t("media:feed.server"), icon: "server", color: SERVER };
    const out: Entry[] = arrivals.map((item) => ({
      key: `a:${item.object_id}`,
      at: item.at,
      source: server,
      forMe: true,
      unread: Boolean(item.unread),
      arrival: item,
    }));
    for (const item of news.values()) {
      out.push({
        key: `n:${item.id}`,
        at: item.published_at,
        source: bySource.get(item.source_id) as Source,
        forMe: (item.mentions ?? []).some(
          (m) => (m.kind === "person" && people.has(m.ref)) || (m.kind === "title" && titles.has(m.ref)),
        ),
        unread: since !== null && Date.parse(item.published_at) > since,
        news: item,
      });
    }
    out.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
    return { entries: out, sources: [server, ...bySource.values()] };
  }, [arrivals, follows, seenAt, mine.data, editorial.data, t]);
  const shown = entries.filter((e) => only === "all" || (only === "mine" ? e.forMe : e.source.key === only));
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
    <section className="feed-section" aria-labelledby="feed-stream">
      <h2 id="feed-stream" className="visually-hidden">
        {t("media:feed.title")}
      </h2>
      <fieldset className="feed-filters">
        <legend className="visually-hidden">{t("media:feed.filter")}</legend>
        <button type="button" aria-pressed={only === "all"} onClick={() => setOnly("all")}>
          {t("media:feed.all")}
        </button>
        <button type="button" aria-pressed={only === "mine"} onClick={() => setOnly("mine")}>
          <Icon name="sparkles" size={14} />
          {t("media:feed.forMe")}
        </button>
        {sources.map((source) => (
          <button
            key={source.key}
            type="button"
            aria-pressed={only === source.key}
            onClick={() => setOnly(only === source.key ? "all" : source.key)}
            style={{ "--badge": source.color } as CSSProperties}
            className="feed-filters__source"
          >
            <span className="feed-filters__dot" aria-hidden="true" />
            {source.label}
          </button>
        ))}
      </fieldset>
      {shown.length ? (
        <ol className="feed-stream">
          {shown.map((entry) => {
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
      ) : (
        <p className="admin-muted">{t("media:feed.nothingYet")}</p>
      )}
    </section>
  );
}
