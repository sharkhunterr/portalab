import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import "./news.css";

export type SourceItem = components["schemas"]["SourceItemOut"];

interface Asked {
  title?: string[];
  person?: string[];
  source?: string[];
}

export function useSourceItems(asked: Asked = {}, limit = 12, enabled = true) {
  return useQuery({
    queryKey: ["news", "sources", "items", asked, limit],
    enabled,
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/news/sources/items", { params: { query: { ...asked, limit } } })).data?.items ??
      [],
  });
}

/** One item from elsewhere: the portal's copy of its picture, its source and date, its title (to the site),
 * a short summary and the library titles and people it names. */
export function SourceCard({ item, actions }: { item: SourceItem; actions?: ReactNode }) {
  const t = useT();
  const format = useFormat();
  const ago = (Date.parse(item.published_at) - Date.now()) / 1000;
  return (
    <li
      className="news-source-card"
      data-pinned={item.pinned || undefined}
      data-hidden={item.hidden || undefined}
    >
      <span className="news-source-card__picture" aria-hidden="true">
        {item.picture ? (
          <img src={item.picture} alt="" loading="lazy" />
        ) : (
          <Icon name="newspaper" size={28} />
        )}
      </span>
      <span className="news-source-card__text">
        <span className="news-source-card__meta">
          {item.pinned ? <Icon name="pin" size={12} /> : null}
          {item.source} · {format.relative(ago)}
        </span>
        <a href={item.link} target="_blank" rel="noopener noreferrer" className="news-source-card__title">
          {item.title}
          <Icon name="external" size={12} />
          <span className="visually-hidden">{t("news:external.opensSite")}</span>
        </a>
        {item.summary ? <span className="news-source-card__summary">{item.summary}</span> : null}
        {item.mentions?.length ? (
          <span className="news-source-card__mentions">
            {item.mentions.slice(0, 4).map((m) => (
              <Link key={`${m.kind}:${m.ref}`} to={m.route} className="feed-chip">
                <Icon name={m.kind === "person" ? "user" : "film"} size={12} />
                {m.label}
              </Link>
            ))}
          </span>
        ) : null}
        {actions ? <span className="news-source__actions">{actions}</span> : null}
      </span>
    </li>
  );
}

/**
 * #299: news from elsewhere — on « À la une » (a channel's when one is chosen), on a title's or a person's
 * page (« in the news »), in « Mon fil » for what I follow. Nothing drawn when there is none.
 */
export function ExternalNews({
  heading,
  asked = {},
  limit = 6,
  category,
  enabled = true,
}: {
  heading: string;
  asked?: Asked;
  limit?: number;
  category?: string | null;
  enabled?: boolean;
}) {
  const items = useSourceItems(asked, limit, enabled);
  const shown = (Array.isArray(items.data) ? items.data : []).filter(
    (item) => !category || item.category_id === category,
  );
  if (!shown.length) return null;
  return (
    <section className="news-external" aria-label={heading}>
      <h3 className="news-page__section">
        <Icon name="rss" size={18} /> {heading}
      </h3>
      <ul className="news-external__list">
        {shown.map((item) => (
          <SourceCard key={item.id} item={item} />
        ))}
      </ul>
    </section>
  );
}
