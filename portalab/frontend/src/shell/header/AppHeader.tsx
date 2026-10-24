import { Link, useLocation } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import type { DeviceClass } from "../../design-system/components/Layout";
import { PluginSlot } from "../../features/plugins/slots/PluginSlot";
import { useT } from "../../i18n/hooks/useT";
import { MenuWaiting } from "../nav/MenuWaiting";
import { usePalette } from "../palette/PaletteContext";
import { RegionBoundary } from "../router/RouteBoundary";
import { useSite } from "../site/site";
import { useSlots } from "../slots/providers";
import { useShellStrings } from "../strings";
import { HeaderSearch } from "./HeaderSearch";
import { type PersonalEntry, PersonalMenu } from "./PersonalMenu";
import { ControlCenterButton } from "./PortalStatus";
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
  const site = useSite(); // issue 159: the site's name, short name and logo
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
          <ControlCenterButton />
          <PluginSlot name="header.action" compact />
          <HelpButton />
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
        <a className="shell-brand" href="/" aria-label={site.name}>
          {site.logo ? (
            <img className="shell-brand__logo" src={site.logo} alt="" />
          ) : (
            <span className="shell-brand__mark" aria-hidden="true">
              <Icon name="sparkles" size={18} />
            </span>
          )}
          {phone ? (
            site.custom ? (
              <span className="shell-brand__name" aria-hidden="true">
                {site.short_name}
              </span>
            ) : null
          ) : (
            <span className="shell-brand__name">{site.name}</span>
          )}
        </a>
      </div>
      {bottomBar ? null : (
        <div className="shell-header__search">{phone ? <SearchField compact /> : <HeaderSearch />}</div>
      )}
      <div className="shell-header__end">
        <ControlCenterButton />
        <PluginSlot name="header.action" compact />
        <HelpButton />
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

/** Issue 202: the guide's page about the page shown (its help key), when the member may read one. */
export function HelpButton() {
  const { help } = useSlots();
  const location = useLocation();
  const target = help?.resolve(location.pathname);
  if (!target) return null;
  return (
    <Link
      to={target.href}
      className="ds-button ds-button--ghost ds-button--icon"
      aria-label={target.label}
      title={target.label}
      data-tour="help"
    >
      <Icon name="help" />
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
