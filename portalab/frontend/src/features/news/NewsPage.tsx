import { useId, useState } from "react";
import { Link } from "react-router";
import { PageHeader } from "../../design-system/components/PageHeader";
import { EmptyState } from "../../design-system/components/Placeholders";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type NewsCard, useCategories, useFeatured, useNewsList } from "./api";
import { Cover } from "./cover";
import "./news.css";
import { UnreadDot } from "../dashboard/templates/Templates";

/**
 * News (spec 011 T020, 027 T095): a magazine page — the first featured article as a hero, the other
 * featured ones beside it, category chips, then the latest articles as cards with a generated cover. Each
 * card is one link (its title), the cover is decorative.
 */
type Categories = Map<string, string>;

function categoryName(categories: Categories, id: string | null | undefined, fallback: string): string {
  return (id && categories.get(id)) || fallback;
}

function ArticleCard({
  item,
  categories,
  hero = false,
}: {
  item: NewsCard;
  categories: Categories;
  hero?: boolean;
}) {
  const t = useT();
  const format = useFormat();
  const category = categoryName(categories, item.category_id, t("news:uncategorized"));
  const age = item.published_at ? (Date.parse(item.published_at) - Date.now()) / 1000 : null;
  return (
    <article className="news-card" data-hero={hero || undefined} data-unread={item.unread || undefined}>
      <Cover seed={item.category_id ?? item.slug} label={category} size={hero ? "lg" : "md"} />
      <div className="news-card__body">
        {hero ? <span className="news-card__kicker">{t("news:featured")}</span> : null}
        <h3 className="news-card__title">
          {item.unread ? <UnreadDot /> : null}
          <Link to={`/news/${item.slug}`}>{item.title}</Link>
        </h3>
        {item.summary ? <p className="news-card__summary">{item.summary}</p> : null}
        {age !== null ? (
          <time className="news-meta" dateTime={item.published_at ?? undefined}>
            {format.relative(age)}
          </time>
        ) : null}
      </div>
    </article>
  );
}

export function NewsPage() {
  const t = useT();
  const headingId = useId();
  const [category, setCategory] = useState("");
  const featured = useFeatured();
  const categories = useCategories();
  const list = useNewsList(category || undefined);
  const names: Categories = new Map((categories.data ?? []).map((c) => [c.id, c.name]));
  const [hero, ...others] = featured.data ?? [];
  return (
    <section aria-labelledby={headingId} className="news-page">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="newspaper"
        title={t("news:title")}
        context={t("news:subtitle")}
      />
      {hero && !category ? (
        <section aria-label={t("news:featured")} className="news-featured">
          <ArticleCard item={hero} categories={names} hero />
          {others.length ? (
            <ul className="news-featured__side">
              {others.slice(0, 3).map((item) => (
                <li key={item.id}>
                  <ArticleCard item={item} categories={names} />
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
      {(categories.data ?? []).length > 0 ? (
        <fieldset className="ds-subnav" aria-label={t("news:category")}>
          <button type="button" aria-pressed={!category} onClick={() => setCategory("")}>
            {t("news:allCategories")}
          </button>
          {(categories.data ?? []).map((c) => (
            <button
              key={c.id}
              type="button"
              aria-pressed={category === c.key}
              onClick={() => setCategory(c.key)}
            >
              {c.name}
            </button>
          ))}
        </fieldset>
      ) : null}
      <h3 className="news-page__section">{t("news:latest")}</h3>
      {list.isPending ? <FunctionalState state="loading" /> : null}
      {list.isError ? <FunctionalState state="unavailable" onRetry={() => list.refetch()} /> : null}
      {list.data && list.data.items.length === 0 ? (
        <EmptyState
          icon="newspaper"
          title={t("news:empty")}
          action={category ? { label: t("news:allCategories"), onSelect: () => setCategory("") } : null}
        />
      ) : null}
      {list.data?.items.length ? (
        <ul className="news-grid" aria-label={t("news:latest")}>
          {list.data.items.map((item) => (
            <li key={item.id}>
              <ArticleCard item={item} categories={names} />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export default NewsPage;
