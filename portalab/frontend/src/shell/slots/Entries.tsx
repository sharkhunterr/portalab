import { useLocation } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Menu } from "../../design-system/components/Overlays";
import { usePalette } from "../palette/PaletteContext";
import { shellStrings } from "../strings";
import { useSlots } from "./providers";

/** Search entry (always present): the real search engine (008) when provided, else the command palette. */
export function SearchEntry() {
  const { search } = useSlots();
  const palette = usePalette();
  return (
    <Button
      variant="secondary"
      className="shell-search"
      aria-keyshortcuts="Control+K Meta+K /"
      onClick={() => (search ? search.open() : palette.open())}
    >
      {shellStrings.search} <kbd>⌘K</kbd>
    </Button>
  );
}

/** Assistant entry (always present): degraded, but visible and explained, when unavailable. */
export function AiEntry() {
  const { ai } = useSlots();
  const location = useLocation();
  if (!ai?.available) {
    return (
      <Button
        variant="secondary"
        aria-disabled="true"
        title={shellStrings.assistantUnavailable}
        onClick={() => undefined}
      >
        {shellStrings.assistant}
        <span className="visually-hidden">: {shellStrings.assistantUnavailable}</span>
      </Button>
    );
  }
  return (
    <Button variant="secondary" onClick={() => ai.open({ route: location.pathname })}>
      {shellStrings.assistant}
    </Button>
  );
}

export function NotificationEntry() {
  const { notifications } = useSlots();
  if (!notifications) return null;
  return (
    <Button variant="secondary" onClick={notifications.open}>
      {shellStrings.notifications}
      {notifications.unread ? <span className="ds-badge"> {notifications.unread}</span> : null}
    </Button>
  );
}

/** Contextual help entry fed by 011's ``HelpResolver`` (F17); absent until a resolver is provided. */
export function HelpEntry() {
  const { help } = useSlots();
  const location = useLocation();
  const target = help?.resolve(location.pathname);
  if (!target) return null;
  return (
    <a className="ds-link" href={target.href}>
      {target.label}
    </a>
  );
}

export function IdentityMenu({
  name,
  onSignOut,
  onNavigate,
}: {
  name: string;
  onSignOut: () => void;
  onNavigate: (to: string) => void;
}) {
  return (
    <Menu
      label={shellStrings.account}
      trigger={<Button variant="secondary">{name}</Button>}
      items={[
        {
          key: "account",
          label: shellStrings.labels["nav.account"] ?? "Account",
          onSelect: () => onNavigate("/account"),
        },
        {
          key: "appearance",
          label: shellStrings.labels["nav.appearance"] ?? "Appearance",
          onSelect: () => onNavigate("/settings/appearance"),
        },
        { key: "signout", label: shellStrings.signOut, onSelect: onSignOut },
      ]}
    />
  );
}
