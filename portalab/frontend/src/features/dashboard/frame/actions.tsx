import { createContext, type ReactNode, useContext } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router";
import { Icon } from "../../../design-system/components/Icon";

/**
 * 027 (#25): a widget's own buttons in its frame's header (« new ticket »…), next to « +N ». The frame
 * provides the slot; a widget renders ``<WidgetHeaderAction>`` anywhere in its content. In the « see all »
 * dialog there is no slot, so the action shows once.
 */
export const HeaderSlot = createContext<HTMLElement | null>(null);

export function WidgetHeaderAction({ children }: { children: ReactNode }) {
  const slot = useContext(HeaderSlot);
  return slot ? createPortal(children, slot) : null;
}

/** A widget's way to its page (« Open the shop », « All my tickets »…), in its header — quieter than an
 * action button: an outline pill with an arrow. */
export function WidgetHeaderLink({ to, label }: { to: string; label: string }) {
  return (
    <WidgetHeaderAction>
      <Link to={to} className="widget-frame__link" title={label}>
        <span>{label}</span>
        <Icon name="chevron-right" size={12} />
      </Link>
    </WidgetHeaderAction>
  );
}
