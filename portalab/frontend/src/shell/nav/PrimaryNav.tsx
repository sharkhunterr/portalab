import { NavLink } from "react-router";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useShellStrings } from "../strings";
import { useNavigationView } from "./NavigationProvider";

/** Primary navigation (spec 004 T018): server-filtered groups and entries; current page marked. */
export function PrimaryNav({ onNavigate }: { onNavigate?: () => void }) {
  const shellStrings = useShellStrings();
  const { view, loading, failed } = useNavigationView();
  if (loading) return <FunctionalState state="loading" label={shellStrings.mainNav} />;
  if (failed || view.degraded) {
    return <FunctionalState state="partial" label={shellStrings.navDegraded} />;
  }
  return (
    <div className="shell-nav">
      {view.groups.map((group) => (
        <section key={group.key} aria-labelledby={`nav-group-${group.key}`}>
          <h2 id={`nav-group-${group.key}`} className="shell-nav__group">
            {shellStrings.label(group.label_key)}
          </h2>
          <ul className="ds-list">
            {group.entries.map((entry) => (
              <li key={entry.key}>
                <NavLink
                  to={entry.route ?? "/"}
                  end={entry.route === "/" || entry.route === "/admin"}
                  className="shell-nav__link"
                  onClick={onNavigate}
                >
                  {shellStrings.label(entry.label_key)}
                </NavLink>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
