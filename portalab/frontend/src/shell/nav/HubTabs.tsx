import { NavLink, useLocation } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { useShellStrings } from "../strings";
import { useNavigationView } from "./NavigationProvider";
import { currentEntry, currentHub } from "./SectionNav";

/**
 * Administration hub tabs (027): the pages of the hub holding the current page, above the content — one
 * place per subject (support, communication, services…) instead of pages scattered in the menu. Only the
 * pages the viewer may open are listed (the server filters the navigation); hidden with a single page.
 */
export function HubTabs() {
  const strings = useShellStrings();
  const location = useLocation();
  const { view } = useNavigationView();
  const hub = currentHub(view.sections, location.pathname);
  if (!hub || hub.entries.length < 2) return null;
  const current = currentEntry(view.sections, location.pathname);
  return (
    <nav className="hub-tabs" aria-label={strings.label(hub.label_key)}>
      <p className="hub-tabs__title">
        <Icon name={hub.icon ?? "settings"} size={24} />
        {strings.label(hub.label_key)}
      </p>
      <ul>
        {hub.entries.map((entry) => (
          <li key={entry.key}>
            <NavLink
              to={entry.route ?? "/admin"}
              end
              aria-current={entry.key === current?.key ? "page" : undefined}
              data-active={entry.key === current?.key ? "true" : undefined}
            >
              {entry.icon ? <Icon name={entry.icon} size={16} /> : null}
              {strings.label(entry.label_key)}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
