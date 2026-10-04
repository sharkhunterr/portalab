import { Avatar } from "../../design-system/components/Avatar";
import type { MenuItem } from "../../design-system/components/Overlays";
import { Menu } from "../../design-system/components/Overlays";
import { useShellStrings } from "../strings";

/**
 * Personal menu behind the avatar (spec 027 FR-003/FR-012): profile and progression, then the user's
 * personal destinations (account, appearance, language, notification preferences, privacy, linked
 * accounts — the server-filtered ``personal`` navigation), then sign out. Radix menu: keyboard and touch.
 */
export interface PersonalEntry {
  key: string;
  label_key: string;
  icon?: string | null;
  route?: string | null;
}

export interface PersonalMenuProps {
  name: string;
  userId?: string | undefined;
  avatarUrl?: string | null | undefined;
  entries: readonly PersonalEntry[];
  onNavigate: (to: string) => void;
  onSignOut: () => void;
  showName?: boolean;
}

export function PersonalMenu({
  name,
  userId,
  avatarUrl,
  entries,
  onNavigate,
  onSignOut,
  showName = false,
}: PersonalMenuProps) {
  const strings = useShellStrings();
  const items: MenuItem[] = [
    { key: "profile", label: strings.profile, icon: "user", onSelect: () => onNavigate("/account") },
    {
      key: "progression",
      label: strings.progression,
      icon: "trophy",
      onSelect: () => onNavigate("/progression"),
    },
    ...entries
      .filter((entry) => entry.route && entry.route !== "/account")
      .map((entry, index) => ({
        key: entry.key,
        label: strings.label(entry.label_key),
        icon: entry.icon ?? undefined,
        separated: index === 0,
        onSelect: () => onNavigate(entry.route as string),
      })),
    { key: "signout", label: strings.signOut, icon: "logout", separated: true, onSelect: onSignOut },
  ];
  return (
    <Menu
      label={strings.personalMenu}
      align="end"
      header={
        <span className="shell-me">
          <Avatar name={name} userId={userId} src={avatarUrl} size="lg" decorative />
          <span className="shell-me__name">{name}</span>
        </span>
      }
      trigger={
        <button type="button" className="shell-avatar-button" aria-label={`${strings.personalMenu}: ${name}`}>
          <Avatar name={name} userId={userId} src={avatarUrl} decorative />
          {showName ? <span className="shell-avatar-button__name">{name}</span> : null}
        </button>
      }
      items={items}
    />
  );
}
