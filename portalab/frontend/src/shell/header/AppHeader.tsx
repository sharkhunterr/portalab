import { useLocation } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import type { DeviceClass } from "../../design-system/components/Layout";
import { useT } from "../../i18n/hooks/useT";
import { usePalette } from "../palette/PaletteContext";
import { RegionBoundary } from "../router/RouteBoundary";
import { useSlots } from "../slots/providers";
import { useShellStrings } from "../strings";
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
  return (
    <header className="shell-header" data-device={device}>
      <div className="shell-header__start">
        {onOpenNavigation ? (
          <Button variant="ghost" size="icon" aria-label={strings.openNavigation} onClick={onOpenNavigation}>
            <Icon name="menu" />
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
        <div className="shell-header__search">
          <SearchField compact={phone} />
        </div>
      )}
      <div className="shell-header__end">
        <AssistantButton />
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

function AssistantButton() {
  const strings = useShellStrings();
  const { ai } = useSlots();
  const location = useLocation();
  const available = Boolean(ai?.available);
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={available ? strings.assistant : `${strings.assistant}: ${strings.assistantUnavailable}`}
      aria-disabled={available ? undefined : "true"}
      title={available ? strings.assistant : strings.assistantUnavailable}
      onClick={() => (available ? ai?.open({ route: location.pathname }) : undefined)}
    >
      <Icon name="sparkles" />
    </Button>
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
