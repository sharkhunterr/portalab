import { useId } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { SafeHtml } from "../content/SafeHtml";
import { usePage, useWikiActions } from "./api";

/** Wiki page (spec 011 T012): breadcrumbs, outline, sanitized content, state and editing actions. */
export function PageView() {
  const t = useT();
  const { slug = "" } = useParams();
  const headingId = useId();
  const page = usePage(slug);
  const { publish } = useWikiActions();
  if (page.isPending) return <FunctionalState state="loading" />;
  if (page.isError || !page.data) return <FunctionalState state="unavailable" label={t("wiki:notFound")} />;
  const data = page.data;
  return (
    <article aria-labelledby={headingId} className="wiki-page">
      {data.breadcrumbs?.length ? (
        <nav aria-label={t("wiki:breadcrumbs")}>
          <ol className="wiki-breadcrumbs">
            {(data.breadcrumbs ?? []).map((crumb) => (
              <li key={crumb.id}>
                <Link to={`/wiki/${crumb.slug}`}>{crumb.title}</Link>
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
      <PageHeader titleId={headingId} level={2} icon="book" title={data.title} />
      {data.status !== "published" ? <p className="wiki-badge">{t(`wiki:status.${data.status}`)}</p> : null}
      {data.translation_missing ? <p role="note">{t("wiki:notTranslated")}</p> : null}
      {data.can_edit ? (
        <div className="ds-stack ds-stack--row">
          <Link to={`/wiki/${data.slug}/edit`}>{t("wiki:edit")}</Link>
          <Link to={`/wiki/${data.slug}/history`}>{t("wiki:history")}</Link>
          {data.status === "draft" ? (
            <Button variant="secondary" onClick={() => publish.mutate({ id: data.id, action: "publish" })}>
              {t("wiki:publish")}
            </Button>
          ) : null}
        </div>
      ) : null}
      {data.outline.length > 1 ? (
        <nav aria-label={t("wiki:outline")}>
          <ol>
            {data.outline.map((entry) => (
              <li key={String(entry.anchor)}>
                <a href={`#${String(entry.anchor)}`}>{String(entry.text)}</a>
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
      <SafeHtml html={data.html} />
    </article>
  );
}

export default PageView;
