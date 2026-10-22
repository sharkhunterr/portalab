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

/** A group of the wiki: a top-level page and its sub-pages, or the top-level pages that have none. */
export interface WikiGroup {
  /** The section page, or ``null`` for the loose top-level pages. */
  root: TreeNode | null;
  /** The pages to read in order (the section page first). */
  pages: TreeNode[];
}

export function groupsOf(tree: TreeNode[]): WikiGroup[] {
  const sections = tree.filter((node) => node.children.length);
  const loose = tree.filter((node) => !node.children.length);
  return [
    ...sections.map((root) => ({ root, pages: flatten([root]) })),
    ...(loose.length ? [{ root: null, pages: loose }] : []),
  ];
}

/** The group a page belongs to. */
export function groupOf(tree: TreeNode[], slug: string): WikiGroup | undefined {
  return groupsOf(tree).find((group) => group.pages.some((node) => node.slug === slug));
}
