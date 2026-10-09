import { createContext, type ReactNode, useContext } from "react";
import { createPortal } from "react-dom";

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
