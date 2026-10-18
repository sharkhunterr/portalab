import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router";
import { api } from "../../api/client";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import type { DeviceClass } from "../../design-system/components/Layout";
import { PluginSlot } from "../../features/plugins/slots/PluginSlot";
import { useT } from "../../i18n/hooks/useT";
import { MenuWaiting } from "../nav/MenuWaiting";
import { useNavigationView } from "../nav/NavigationProvider";
import { usePalette } from "../palette/PaletteContext";
import { RegionBoundary } from "../router/RouteBoundary";
import { useSlots } from "../slots/providers";
import { useShellStrings } from "../strings";
import { HeaderSearch } from "./HeaderSearch";
import { type PersonalEntry, PersonalMenu } from "./PersonalMenu";
import { ProgressChip } from "./ProgressChip";
import type { useHeaderData } from "./useHeaderData";

/**
 * The personal header (spec 027 US1, FR-001…FR-007): menu control, brand, search, assistant, notifications
 * with their unread count, level + XP and Coins, and the avatar opening the personal menu. Each data element
 * renders and fails on its own; search, menu, notifications and sign out are always there. The theme picks
 * the arrangement (``data-header``) and the placement — top bar or footer bar (``data-header-position``).
 */
export interface AppHeaderProps {
  device: DeviceClass;
  /** Header data, read once by the shell (one live subscription). */
  data: ReturnType<typeof useHeaderData>;
  /** Shown until the account is loaded. */
  fallbackName?: string;
  /** A phone bottom bar already offers search and notifications: the header does not repeat them. */
  bottomBar?: boolean;
  personal: readonly PersonalEntry[];
  onNavigate: (to: string) => void;
  onSignOut: () => void;
  /** Shown when the navigation lives in a panel the header opens (drawer/orbit variants). */
  onOpenNavigation?: (() => void) | undefined;
}

export function AppHeader({
  device,
  data,
  fallbackName = "",
  bottomBar = false,
  personal,
  onNavigate,
  onSignOut,
  onOpenNavigation,
}: AppHeaderProps) {
  const strings = useShellStrings();
  const phone = device === "phone";
  const name = data.me?.display_name ?? data.me?.login ?? fallbackName;
  // 027: on a phone with the menu in a panel, the header keeps the essentials — home and search on the
  // left; incidents, level and Coins, notifications and the menu on the right (the profile lives in the menu)
  const compactPhone = phone && Boolean(onOpenNavigation);
  if (compactPhone) {
    return (
      <header className="shell-header" data-device={device} data-compact="true">
        <div className="shell-header__start">
          <Link to="/" className="ds-button ds-button--ghost ds-button--icon" aria-label={strings.home}>
            <Icon name="home" />
          </Link>
          <HeaderSearch phone />
        </div>
        <div className="shell-header__end">
          <IncidentsButton />
          <PluginSlot name="header.action" compact />
          {data.progression ? (
            <RegionBoundary resetKey="progression">
              <ProgressChip progression={data.progression} compact />
            </RegionBoundary>
          ) : null}
          <NotificationButton unread={data.unread} />
          <Button
            variant="ghost"
            size="icon"
            data-tour="nav"
            aria-label={strings.openNavigation}
            onClick={onOpenNavigation}
          >
            <Icon name="menu" />
            <MenuWaiting />
          </Button>
        </div>
      </header>
    );
  }
  return (
    <header className="shell-header" data-device={device}>
      <div className="shell-header__start">
        {onOpenNavigation ? (
          <Button
            variant="ghost"
            size="icon"
            data-tour="nav"
            aria-label={strings.openNavigation}
            onClick={onOpenNavigation}
          >
            <Icon name="menu" />
            <MenuWaiting />
          </Button>
        ) : null}
        <a className="shell-brand" href="/" aria-label={strings.brand}>
          <span className="shell-brand__mark" aria-hidden="true">
            <Icon name="sparkles" size={18} />
          </span>
          {phone ? null : <span className="shell-brand__name">{strings.brand}</span>}
        </a>
      </div>
      {bottomBar ? null : (
        <div className="shell-header__search">{phone ? <SearchField compact /> : <HeaderSearch />}</div>
      )}
      <div className="shell-header__end">
        <AssistantButton />
        <IncidentsButton />
        <PluginSlot name="header.action" compact />
        {bottomBar ? null : <NotificationButton unread={data.unread} />}
        {data.progression ? (
          <RegionBoundary resetKey="progression">
            <ProgressChip progression={data.progression} compact={phone} />
          </RegionBoundary>
        ) : null}
        <PersonalMenu
          name={name}
          userId={data.me?.id}
          avatarUrl={data.avatarUrl}
          entries={personal}
          onNavigate={onNavigate}
          onSignOut={onSignOut}
          showName={device === "desktop"}
        />
      </div>
    </header>
  );
}

/** Search entry (FR-015): a wide field-like button on tablet/desktop, an icon on phones. */
function SearchField({ compact }: { compact: boolean }) {
  const strings = useShellStrings();
  const { search } = useSlots();
  const palette = usePalette();
  const open = () => (search ? search.open() : palette.open());
  if (compact) {
    return (
      <Button
        variant="ghost"
        size="icon"
        data-tour="search"
        aria-label={strings.search}
        aria-keyshortcuts="Control+K Meta+K /"
        onClick={open}
      >
        <Icon name="search" />
      </Button>
    );
  }
  return (
    <button type="button" className="shell-search" aria-keyshortcuts="Control+K Meta+K /" onClick={open}>
      <Icon name="search" size={18} />
      <span className="shell-search__label">{strings.searchPlaceholder}</span>
      <span className="shell-search__kbd" aria-hidden="true">
        ⌘K
      </span>
      <span className="visually-hidden">{strings.search}</span>
    </button>
  );
}

/** The assistant, only when one is available (027: an inert button helped nobody). */
function AssistantButton() {
  const strings = useShellStrings();
  const { ai } = useSlots();
  const location = useLocation();
  if (!ai?.available) return null;
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={strings.assistant}
      title={strings.assistant}
      onClick={() => ai.open({ route: location.pathname })}
    >
      <Icon name="sparkles" />
    </Button>
  );
}

/**
 * 027: the portal's health at a glance — all good, degraded (with the number of services in trouble) or
 * incident (with the number of incidents in progress); it opens the service status page.
 */
export function IncidentsButton() {
  const t = useT();
  const { view } = useNavigationView();
  const canRead = view.groups.some((g) => g.entries.some((e) => e.key === "health.services"));
  const open = useQuery({
    queryKey: ["incidents", "open"],
    retry: false,
    refetchInterval: 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/incidents", { params: { query: { state: "open" } } })).data ??
        []) as unknown[],
  });
  const services = useQuery({
    queryKey: ["shell", "health-summary"],
    enabled: canRead,
    retry: false,
    refetchInterval: 60_000,
    queryFn: async () =>
      (
        (await api.GET("/api/v1/services/health")).data as unknown as {
          items: Array<{ state: string; degrades_portal?: boolean }>;
        }
      ).items,
  });
  const incidents = Array.isArray(open.data) ? open.data.length : 0;
  const items = Array.isArray(services.data) ? services.data : [];
  // services whose alerting rule leaves them out of the portal's health (internal ones) do not count
  const troubled = items.filter(
    (s) => s.degrades_portal !== false && (s.state === "unavailable" || s.state === "degraded"),
  ).length;
  if (!incidents && !canRead) return null;
  if (!incidents && !items.length) return null;
  const state = incidents ? "incident" : troubled ? "degraded" : "ok";
  const count = incidents || troubled;
  const label =
    state === "incident"
      ? t("shell:incidents", { count })
      : state === "degraded"
        ? t("shell:health.degraded", { count })
        : t("shell:health.ok");
  return (
    <Link
      to="/services"
      className="ds-button ds-button--ghost ds-button--icon shell-health"
      data-state={state}
      aria-label={label}
      title={label}
    >
      <Icon name={state === "incident" ? "alert" : state === "degraded" ? "warning" : "heart"} />
      {state === "ok" ? null : (
        <span className="shell-health__count" aria-hidden="true">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}

export function NotificationButton({ unread }: { unread: number | null }) {
  const strings = useShellStrings();
  const t = useT();
  const { notifications } = useSlots();
  const count = unread ?? 0;
  const label =
    unread === null ? strings.notifications : `${strings.notifications}: ${t("shell:unread", { count })}`;
  return (
    <Button
      variant="ghost"
      size="icon"
      className="shell-bell"
      aria-label={label}
      onClick={() => notifications?.open()}
    >
      <Icon name="bell" />
      {count > 0 ? (
        <span className="shell-bell__count" aria-hidden="true">
          {count > 99 ? "99+" : count}
        </span>
      ) : null}
    </Button>
  );
}
