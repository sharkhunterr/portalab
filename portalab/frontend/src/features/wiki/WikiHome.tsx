import { useId, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { EmptyState } from "../../design-system/components/Placeholders";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { type TreeNode, useTree } from "./api";
import { flatten, WikiTree } from "./WikiTree";
import "./wiki.css";

/**
 * Wiki home (spec 011 T016, 027 T095): "New page" as the primary action, a title filter, and the top-level
 * pages as cards listing their sub-pages — the viewer only receives the pages they may read.
 */
/** Sub-pages listed on a card; the others are one click away, on the section's page. */
const SHOWN = 6;

function Section({ node }: { node: TreeNode }) {
  const t = useT();
  return (
    <li className="ds-card wiki-section">
      <span className="wiki-section__icon" aria-hidden="true">
        <Icon name="book" size={22} />
      </span>
      <h3 className="wiki-section__title">
        <Link to={`/wiki/${node.slug}`}>{node.title}</Link>
        {node.status !== "published" ? (
          <span className="ds-badge wiki-badge">{t(`wiki:status.${node.status}`)}</span>
        ) : null}
      </h3>
      <p className="wiki-meta">{t("wiki:subpages", { count: flatten(node.children).length })}</p>
      {node.children.length ? <WikiTree nodes={node.children.slice(0, SHOWN)} /> : null}
      {node.children.length > SHOWN ? (
        <Link className="wiki-more" to={`/wiki/${node.slug}`}>
          {t("wiki:more", { count: node.children.length - SHOWN })}
        </Link>
      ) : null}
    </li>
  );
}

export function WikiHome() {
  const t = useT();
  const headingId = useId();
  const tree = useTree();
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const matches = needle
    ? flatten(tree.data ?? []).filter((node) => node.title.toLowerCase().includes(needle))
    : [];
  return (
    <section aria-labelledby={headingId} className="wiki-home">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="book"
        title={t("wiki:title")}
        context={t("wiki:subtitle")}
        primary={
          <Link className="ds-button ds-button--primary" to="/wiki/new">
            <Icon name="plus" size={18} />
            {t("wiki:new")}
          </Link>
        }
      />
      {tree.isPending ? <FunctionalState state="loading" /> : null}
      {tree.isError ? <FunctionalState state="unavailable" onRetry={() => tree.refetch()} /> : null}
      {tree.data && tree.data.length === 0 ? (
        <EmptyState
          icon="book"
          title={t("wiki:empty")}
          action={
            <Link className="ds-button ds-button--primary" to="/wiki/new">
              {t("wiki:new")}
            </Link>
          }
        />
      ) : null}
      {tree.data?.length ? (
        <>
          <label className="wiki-search">
            <Icon name="search" size={18} />
            <span className="visually-hidden">{t("wiki:search")}</span>
            <input
              type="search"
              value={query}
              placeholder={t("wiki:search")}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          {needle ? (
            matches.length ? (
              <ul className="wiki-results" aria-label={t("wiki:search")}>
                {matches.map((node) => (
                  <li key={node.id}>
                    <Link to={`/wiki/${node.slug}`}>
                      <Icon name="book" size={16} />
                      {node.title}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="wiki-meta">{t("wiki:noMatch", { query })}</p>
            )
          ) : (
            <nav aria-label={t("wiki:tree")}>
              <ul className="wiki-sections">
                {tree.data.map((node) => (
                  <Section key={node.id} node={node} />
                ))}
              </ul>
            </nav>
          )}
        </>
      ) : null}
    </section>
  );
}

export default WikiHome;
