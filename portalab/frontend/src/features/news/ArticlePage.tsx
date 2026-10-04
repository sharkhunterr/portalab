import { useId } from "react";
import { useParams } from "react-router";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { SafeHtml } from "../content/SafeHtml";
import { useArticle } from "./api";

/** One article (spec 011 T020): sanitized body; archived and untranslated states said in text. */
export function ArticlePage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const { slug = "" } = useParams();
  const article = useArticle(slug);
  if (article.isPending) return <FunctionalState state="loading" />;
  if (article.isError || !article.data)
    return <FunctionalState state="unavailable" label={t("news:notFound")} />;
  const data = article.data;
  return (
    <article aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="newspaper" title={data.title} />
      {data.published_at ? <p className="news-meta">{format.dateTime(data.published_at)}</p> : null}
      {data.archived ? <p role="note">{t("news:archived")}</p> : null}
      {data.translation_missing ? <p role="note">{t("news:notTranslated")}</p> : null}
      {data.summary ? <p className="news-summary">{data.summary}</p> : null}
      <SafeHtml html={data.html} />
    </article>
  );
}

export default ArticlePage;
