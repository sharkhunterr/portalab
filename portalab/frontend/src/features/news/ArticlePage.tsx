import { useId } from "react";
import { Link, useParams } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { SafeHtml } from "../content/SafeHtml";
import { useArticle, useCategories } from "./api";
import { Cover, readingMinutes } from "./cover";
import "./news.css";

/**
 * One article (spec 011 T020, 027 T095): a cover banner with category, date and reading time, then the
 * sanitized body in a readable column. Archived and untranslated states are said in text.
 */
export function ArticlePage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const { slug = "" } = useParams();
  const article = useArticle(slug);
  const categories = useCategories();
  if (article.isPending) return <FunctionalState state="loading" />;
  if (article.isError || !article.data)
    return <FunctionalState state="unavailable" label={t("news:notFound")} />;
  const data = article.data;
  const category =
    (categories.data ?? []).find((c) => c.id === data.category_id)?.name ?? t("news:uncategorized");
  const text = data.html.replace(/<[^>]+>/g, " ");
  return (
    <article aria-labelledby={headingId} className="news-article">
      <Link to="/news" className="news-article__back">
        <Icon name="chevron-left" size={16} />
        {t("news:back")}
      </Link>
      <div className="news-article__hero">
        <Cover seed={data.category_id ?? data.slug} size="lg" />
        <div className="news-article__heading">
          <span className="news-card__kicker">{category}</span>
          <PageHeader
            titleId={headingId}
            level={2}
            title={data.title}
            context={[
              data.published_at ? format.dateTime(data.published_at) : null,
              t("news:readingTime", { minutes: readingMinutes(text) }),
            ]
              .filter(Boolean)
              .join(" · ")}
          />
        </div>
      </div>
      {data.archived ? <p role="note">{t("news:archived")}</p> : null}
      {data.translation_missing ? <p role="note">{t("news:notTranslated")}</p> : null}
      {data.summary ? <p className="news-article__lead">{data.summary}</p> : null}
      <div className="news-article__body">
        <SafeHtml html={data.html} />
      </div>
    </article>
  );
}

export default ArticlePage;
