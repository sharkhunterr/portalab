import { useId, useState } from "react";
import { Link } from "react-router";
import { SelectField } from "../../design-system/components/Field";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type NewsCard, useCategories, useFeatured, useNewsList } from "./api";

/** News (spec 011 T020): the featured shelf, then the latest articles, filterable by category. */
function Cards({ items, label }: { items: NewsCard[]; label: string }) {
  const format = useFormat();
  return (
    <ul className="news-list" aria-label={label}>
      {items.map((item) => (
        <li key={item.id}>
          <Link to={`/news/${item.slug}`}>{item.title}</Link>
          {item.published_at ? (
            <span className="news-meta"> · {format.dateTime(item.published_at)}</span>
          ) : null}
          {item.summary ? <p>{item.summary}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export function NewsPage() {
  const t = useT();
  const headingId = useId();
  const [category, setCategory] = useState("");
  const featured = useFeatured();
  const categories = useCategories();
  const list = useNewsList(category || undefined);
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{t("news:title")}</h2>
      {featured.data?.length ? (
        <section aria-label={t("news:featured")}>
          <h3>{t("news:featured")}</h3>
          <Cards items={featured.data} label={t("news:featured")} />
        </section>
      ) : null}
      <SelectField label={t("news:category")} value={category} onChange={(e) => setCategory(e.target.value)}>
        <option value="">{t("news:allCategories")}</option>
        {(categories.data ?? []).map((c) => (
          <option key={c.id} value={c.key}>
            {c.name}
          </option>
        ))}
      </SelectField>
      {list.isPending ? <FunctionalState state="loading" /> : null}
      {list.isError ? <FunctionalState state="unavailable" onRetry={() => list.refetch()} /> : null}
      {list.data && list.data.items.length === 0 ? <p>{t("news:empty")}</p> : null}
      {list.data ? <Cards items={list.data.items} label={t("news:latest")} /> : null}
    </section>
  );
}

export default NewsPage;
