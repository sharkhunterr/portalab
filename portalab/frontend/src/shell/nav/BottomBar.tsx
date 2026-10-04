import { NavLink } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { usePalette } from "../palette/PaletteContext";
import { useSlots } from "../slots/providers";
import { useShellStrings } from "../strings";

/**
 * Phone bottom bar (spec 027 FR-019): the most important destinations one tap away — Home, Search,
 * Notifications (with its count) and the Menu that opens every section. Safe-area aware.
 */
export function BottomBar({
  unread,
  onOpenMenu,
  menuOpen,
}: {
  unread: number | null;
  onOpenMenu: () => void;
  menuOpen: boolean;
}) {
  const strings = useShellStrings();
  const { search, notifications } = useSlots();
  const palette = usePalette();
  const count = unread ?? 0;
  return (
    <nav className="shell-bottom-bar" aria-label={strings.sections}>
      <NavLink to="/" end className="shell-bottom-bar__item">
        <Icon name="home" />
        <span>{strings.home}</span>
      </NavLink>
      <button
        type="button"
        className="shell-bottom-bar__item"
        onClick={() => (search ? search.open() : palette.open())}
      >
        <Icon name="search" />
        <span>{strings.search}</span>
      </button>
      <button type="button" className="shell-bottom-bar__item" onClick={() => notifications?.open()}>
        <span className="shell-bottom-bar__icon">
          <Icon name="bell" />
          {count > 0 ? (
            <span className="shell-bell__count" aria-hidden="true">
              {count > 99 ? "99+" : count}
            </span>
          ) : null}
        </span>
        <span>
          {strings.notifications}
          {count > 0 ? <span className="visually-hidden"> ({count})</span> : null}
        </span>
      </button>
      <button type="button" className="shell-bottom-bar__item" aria-expanded={menuOpen} onClick={onOpenMenu}>
        <Icon name="menu" />
        <span>{strings.menu}</span>
      </button>
    </nav>
  );
}
