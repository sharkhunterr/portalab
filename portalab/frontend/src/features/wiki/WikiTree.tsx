import { Link } from "react-router";
import { useT } from "../../i18n/hooks/useT";
import type { TreeNode } from "./api";

/** The wiki page tree (027 T095), shared by the home page and the page sidebar; the current page is marked. */
export function WikiTree({ nodes, current }: { nodes: TreeNode[]; current?: string | undefined }) {
  const t = useT();
  return (
    <ul className="wiki-tree">
      {nodes.map((node) => (
        <li key={node.id}>
          <Link to={`/wiki/${node.slug}`} aria-current={node.slug === current ? "page" : undefined}>
            {node.title}
            {node.status !== "published" ? (
              <span className="ds-badge wiki-badge">{t(`wiki:status.${node.status}`)}</span>
            ) : null}
          </Link>
          {node.children.length ? <WikiTree nodes={node.children} current={current} /> : null}
        </li>
      ))}
    </ul>
  );
}

/** Every node of the tree, depth first (for the title filter). */
export function flatten(nodes: TreeNode[]): TreeNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children)]);
}
