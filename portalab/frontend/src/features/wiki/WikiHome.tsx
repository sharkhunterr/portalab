import { useId } from "react";
import { Link } from "react-router";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { type TreeNode, useTree } from "./api";

/** Wiki home (spec 011 T016): the page tree the viewer may read, as nested lists. */
function Branch({ nodes }: { nodes: TreeNode[] }) {
  const t = useT();
  return (
    <ul className="wiki-tree">
      {nodes.map((node) => (
        <li key={node.id}>
          <Link to={`/wiki/${node.slug}`}>{node.title}</Link>
          {node.status !== "published" ? (
            <span className="wiki-badge"> ({t(`wiki:status.${node.status}`)})</span>
          ) : null}
          {node.children.length ? <Branch nodes={node.children} /> : null}
        </li>
      ))}
    </ul>
  );
}

export function WikiHome() {
  const t = useT();
  const headingId = useId();
  const tree = useTree();
  return (
    <section aria-labelledby={headingId}>
      <PageHeader titleId={headingId} level={2} icon="book" title={t("wiki:title")} />
      <p>
        <Link to="/wiki/new">{t("wiki:new")}</Link>
      </p>
      {tree.isPending ? <FunctionalState state="loading" /> : null}
      {tree.isError ? <FunctionalState state="unavailable" onRetry={() => tree.refetch()} /> : null}
      {tree.data && tree.data.length === 0 ? <p>{t("wiki:empty")}</p> : null}
      <nav aria-label={t("wiki:tree")}>{tree.data ? <Branch nodes={tree.data} /> : null}</nav>
    </section>
  );
}

export default WikiHome;
