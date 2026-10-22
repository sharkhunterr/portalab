import { useId } from "react";
import { Link, useParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { SafeHtml } from "../content/SafeHtml";
import { type TreeNode, usePage, useTree, useWikiActions } from "./api";
import { groupOf, WikiTree } from "./WikiTree";
import "./wiki.css";

/**
 * Wiki page (spec 011 T012, 027 T095): a documentation layout — the page tree on the side (desktop),
 * breadcrumbs, the title with Edit as the primary action, the outline ("On this page") and the sanitized
 * content in a readable column, on a frosted panel so the background never gets in the way of reading.
 * At the end: the previous and next pages of the group, and its contents in a dialog (the side tree is
 * for wide screens only).
 */
function Contents({ title, nodes, current }: { title: string; nodes: TreeNode[]; current: string }) {
  const t = useT();
  return (
    <Dialog
      title={t("wiki:contentsOf", { title })}
      closeLabel={t("wiki:close")}
      trigger={
        <button type="button" className="ds-button ds-button--ghost wiki-contents">
          <Icon name="list" size={16} />
          {t("wiki:contents")}
        </button>
      }
    >
      <nav aria-label={t("wiki:contentsOf", { title })} className="wiki-contents__list">
        <WikiTree nodes={nodes} current={current} />
      </nav>
    </Dialog>
  );
}

function Pager({ prev, next }: { prev?: TreeNode | undefined; next?: TreeNode | undefined }) {
  const t = useT();
  return (
    <nav aria-label={t("wiki:contents")} className="wiki-pager">
      {prev ? (
        <Link className="wiki-pager__link" data-dir="prev" to={`/wiki/${prev.slug}`} rel="prev">
          <Icon name="chevron-left" size={18} />
          <span>
            <span className="wiki-pager__dir">{t("wiki:previous")}</span>
            <span className="wiki-pager__title">{prev.title}</span>
          </span>
        </Link>
      ) : null}
      {next ? (
        <Link className="wiki-pager__link" data-dir="next" to={`/wiki/${next.slug}`} rel="next">
          <span>
            <span className="wiki-pager__dir">{t("wiki:next")}</span>
            <span className="wiki-pager__title">{next.title}</span>
          </span>
          <Icon name="chevron-right" size={18} />
        </Link>
      ) : null}
    </nav>
  );
}

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
  const group = tree.data ? groupOf(tree.data, data.slug) : undefined;
  const at = group ? group.pages.findIndex((node) => node.slug === data.slug) : -1;
  const groupTitle = group?.root?.title ?? t("wiki:loose");
  // the contents list a section as its page and sub-pages; loose pages as themselves
  const contents = group ? (group.root ? [group.root] : group.pages) : [];
  return (
    <div className="wiki-layout">
      <article aria-labelledby={headingId} className="wiki-page">
        <div className="wiki-page__top">
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
          {group && group.pages.length > 1 ? (
            <Contents title={groupTitle} nodes={contents} current={data.slug} />
          ) : null}
        </div>
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
        {group && group.pages.length > 1 ? (
          <footer className="wiki-page__foot">
            <Pager prev={group.pages[at - 1]} next={group.pages[at + 1]} />
            <Contents title={groupTitle} nodes={contents} current={data.slug} />
          </footer>
        ) : null}
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
