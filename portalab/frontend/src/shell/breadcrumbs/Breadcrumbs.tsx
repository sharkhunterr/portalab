import type { ReactNode } from "react";
import { Link, useLocation, useMatches } from "react-router";
import { useNavigationView } from "../nav/NavigationProvider";
import { crumbOf } from "../router/handle";
import { useShellStrings } from "../strings";

/**
 * Breadcrumbs (spec 004 T030; R7, FR-012): built from route handles (static labels or resolved from
 * params), ancestors navigable, the current page marked. Long trails collapse the middle items behind an
 * accessible "…" while keeping the first and the last two.
 */
export function Breadcrumbs({ max = 4 }: { max?: number }) {
  const shellStrings = useShellStrings();
  const matches = useMatches();
  const { view } = useNavigationView();
  const location = useLocation();
  let items = matches
    .map((match) => ({ path: match.pathname, text: crumbOf(match.handle, match.params) }))
    .filter((item): item is { path: string; text: string } => Boolean(item.text));
  const parent = view.crumbs[location.pathname.replace(/\/[^/]+$/, "") || "/"];
  if (parent?.route && !items.some((i) => i.path === parent.route)) {
    items = [{ path: parent.route, text: shellStrings.label(parent.label_key) }, ...items];
  }
  if (items.length <= 1) return null;
  const first = items[0] as { path: string; text: string };
  const shown: Array<{ path: string; text: string } | null> =
    items.length > max ? [first, null, ...items.slice(-2)] : items;
  return (
    <nav aria-label={shellStrings.breadcrumb} className="shell-breadcrumbs">
      <ol>
        {shown.map((item, index) =>
          !item ? (
            <li key="ellipsis">
              <span aria-hidden="true">…</span>
              <span className="visually-hidden">{`${items.length - 3} more levels`}</span>
            </li>
          ) : (
            <li key={item.path}>
              {index === shown.length - 1 ? (
                <span aria-current="page">{item.text}</span>
              ) : (
                <Link to={item.path}>{item.text}</Link>
              )}
            </li>
          ),
        )}
      </ol>
    </nav>
  );
}

/** Contextual links contributed for the current page (spec 004 FR-013). */
export function RelatedLinks() {
  const shellStrings = useShellStrings();
  const { view } = useNavigationView();
  const location = useLocation();
  const links = view.related[location.pathname] ?? [];
  if (!links.length) return null;
  return (
    <aside aria-label={shellStrings.related} className="shell-related">
      <h2 className="shell-nav__group">{shellStrings.related}</h2>
      <ul className="ds-list">
        {links.map((link) => (
          <li key={link.key}>
            <Link to={link.route ?? "/"}>{shellStrings.label(link.label_key)}</Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}

/** Empty states must always offer a next action — no dead ends (spec 004 T030). */
export function EmptyState({
  title,
  children,
  nextAction,
}: {
  title: string;
  children?: ReactNode;
  nextAction: ReactNode;
}) {
  return (
    <section className="ds-panel" aria-label={title}>
      <h2>{title}</h2>
      {children}
      <div className="ds-stack ds-stack--row">{nextAction}</div>
    </section>
  );
}
