import { NavLink, useLocation } from "react-router";
import { CountBadge } from "../../design-system/components/CountBadge";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useShellStrings } from "../strings";
import { useAttention } from "./attention";
import { useNavigationView } from "./NavigationProvider";
import { currentEntry, currentHub, type Hub, isCurrent } from "./SectionNav";

/**
 * Hub tabs (027): the pages of the hub holding the current page, above the content — one place per subject
 * instead of pages scattered in the menu. Administration hubs (support, communication, services…), member
 * sections (media, community, support…) and « My account » work the same way. Only the pages the viewer
 * may open are listed (the server filters the navigation); hidden with a single page.
 */
export function HubTabs() {
  const strings = useShellStrings();
  const t = useT();
  const attention = useAttention();
  const location = useLocation();
  const { view } = useNavigationView();
  // « My account » (027): the personal pages of the avatar menu are a hub too
  const personal = [...view.personal]
    .filter((entry) => isCurrent(entry.route, location.pathname))
    .sort((a, b) => (b.route?.length ?? 0) - (a.route?.length ?? 0))[0];
  const hub: Hub | undefined = personal
    ? { key: "me", label_key: "nav.section.me", icon: "user", entries: view.personal, audience: "personal" }
    : currentHub(view.sections, location.pathname);
  if (!hub || hub.entries.length < 2) return null;
  const current = personal ?? currentEntry(view.sections, location.pathname);
  return (
    <nav className="hub-tabs" data-audience={hub.audience} aria-label={strings.label(hub.label_key)}>
      <p className="hub-tabs__title">
        <Icon name={hub.icon ?? "settings"} size={24} />
        {strings.label(hub.label_key)}
      </p>
      <ul>
        {hub.entries.map((entry) => (
          <li key={entry.key}>
            <NavLink
              to={entry.route ?? "/"}
              end
              aria-current={entry.key === current?.key ? "page" : undefined}
              data-active={entry.key === current?.key ? "true" : undefined}
            >
              {entry.icon ? <Icon name={entry.icon} size={16} /> : null}
              {strings.label(entry.label_key)}
              <CountBadge
                count={attention.of(entry)}
                label={t("shell:attention", { count: attention.of(entry) })}
              />
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
