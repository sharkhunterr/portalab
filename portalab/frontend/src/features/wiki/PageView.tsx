import { useId } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { SafeHtml } from "../content/SafeHtml";
import { usePage, useTree, useWikiActions } from "./api";
import { WikiTree } from "./WikiTree";
import "./wiki.css";

/**
 * Wiki page (spec 011 T012, 027 T095): a documentation layout — the page tree on the side (desktop),
 * breadcrumbs, the title with Edit as the primary action, the outline ("On this page") and the sanitized
 * content in a readable column. On phones everything stacks and the tree moves below the content.
 */
export function PageView() {
  const t = useT();
  const { slug = "" } = useParams();
  const headingId = useId();
  const page = usePage(slug);
  const tree = useTree();
  const { publish } = useWikiActions();
  if (page.isPending) return <FunctionalState state="loading" />;
  if (page.isError || !page.data) return <FunctionalState state="unavailable" label={t("wiki:notFound")} />;
  const data = page.data;
  return (
    <div className="wiki-layout">
      <article aria-labelledby={headingId} className="wiki-page">
        <nav aria-label={t("wiki:breadcrumbs")}>
          <ol className="wiki-breadcrumbs">
            <li>
              <Link to="/wiki">{t("wiki:home")}</Link>
            </li>
            {(data.breadcrumbs ?? []).map((crumb) => (
              <li key={crumb.id}>
                <Link to={`/wiki/${crumb.slug}`}>{crumb.title}</Link>
              </li>
            ))}
          </ol>
        </nav>
        <PageHeader
          titleId={headingId}
          level={2}
          icon="book"
          title={data.title}
          primary={
            data.can_edit ? (
              <Link className="ds-button ds-button--primary" to={`/wiki/${data.slug}/edit`}>
                <Icon name="settings" size={16} />
                {t("wiki:edit")}
              </Link>
            ) : undefined
          }
          secondary={
            data.can_edit ? (
              <>
                <Link className="ds-button ds-button--ghost" to={`/wiki/${data.slug}/history`}>
                  <Icon name="clock" size={16} />
                  {t("wiki:history")}
                </Link>
                {data.status === "draft" ? (
                  <Button
                    variant="secondary"
                    onClick={() => publish.mutate({ id: data.id, action: "publish" })}
                  >
                    {t("wiki:publish")}
                  </Button>
                ) : null}
              </>
            ) : undefined
          }
        />
        {data.status !== "published" ? (
          <p className="ds-badge wiki-badge">{t(`wiki:status.${data.status}`)}</p>
        ) : null}
        {data.translation_missing ? <p role="note">{t("wiki:notTranslated")}</p> : null}
        {data.outline.length > 1 ? (
          <nav aria-label={t("wiki:outline")} className="wiki-outline">
            <p className="wiki-outline__title">{t("wiki:outline")}</p>
            <ol>
              {data.outline.map((entry) => (
                <li key={String(entry.anchor)}>
                  <a href={`#${String(entry.anchor)}`}>{String(entry.text)}</a>
                </li>
              ))}
            </ol>
          </nav>
        ) : null}
        <div className="wiki-content">
          <SafeHtml html={data.html} />
        </div>
      </article>
      {tree.data?.length ? (
        <nav aria-label={t("wiki:browse")} className="wiki-sidebar">
          <p className="wiki-outline__title">{t("wiki:browse")}</p>
          <WikiTree nodes={tree.data} current={data.slug} />
        </nav>
      ) : null}
    </div>
  );
}

export default PageView;
