import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as MenuPrimitive from "@radix-ui/react-dropdown-menu";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import {
  createContext,
  Fragment,
  type MouseEvent,
  type ReactNode,
  useContext,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { Button } from "./Button";
import { Icon } from "./Icon";

/**
 * Overlays on Radix primitives (focus management, Escape to close, focus return, labelled by their
 * title): Dialog, Drawer, Menu, Popover, Tooltip. A tooltip never holds the only copy of information.
 */
export interface DialogProps {
  trigger: ReactNode;
  title: string;
  description?: string;
  children: ReactNode;
  closeLabel?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  variant?: "dialog" | "drawer";
  /** ``lg``: a wider dialog for guided forms (027). */
  size?: "md" | "lg" | "full" | undefined;
  /** 027: actions shown in a footer that stays visible, after the close button (e.g. « Buy »). */
  footer?: ReactNode;
  /** 030: the side a drawer opens from (``end`` by default) */
  side?: "start" | "end" | undefined;
}

/** 027: where a dialog's own actions go — its footer, on the close button's line. */
const FooterSlot = createContext<HTMLElement | null>(null);

/**
 * 027: a dialog's action buttons (« Save », « Send »…), written where they belong — at the end of its form,
 * even in a child component — and shown in the dialog's footer, on the same line as « Cancel ». A submit
 * button still submits the form it was written in (with its validation). Outside a dialog, they stay
 * where they are.
 */
/** Whether this content is inside a dialog (its actions then go to the footer). */
export function useInDialog(): boolean {
  return useContext(FooterSlot) !== null;
}

export function DialogActions({ children }: { children: ReactNode }) {
  const slot = useContext(FooterSlot);
  const marker = useRef<HTMLSpanElement>(null);
  if (!slot) return <>{children}</>;
  const submit = (event: MouseEvent<HTMLSpanElement>) => {
    const button = (event.target as HTMLElement).closest("button");
    if (button?.type !== "submit" || button.form) return;
    const form = marker.current?.closest("form");
    if (!form) return;
    event.preventDefault();
    form.requestSubmit();
  };
  return (
    <>
      {/* the form's own default button: Enter still submits it */}
      <span ref={marker} hidden>
        <button type="submit" tabIndex={-1} aria-hidden="true" />
      </span>
      {createPortal(
        // biome-ignore lint/a11y/noStaticElementInteractions: forwards a click on a submit button to its form
        // biome-ignore lint/a11y/useKeyWithClickEvents: buttons fire click on Enter and Space
        <span className="ds-dialog__actions" onClick={submit}>
          {children}
        </span>,
        slot,
      )}
    </>
  );
}

export function Dialog({
  trigger,
  title,
  description,
  children,
  closeLabel = "Close",
  open,
  onOpenChange,
  variant = "dialog",
  size = "md",
  footer,
  side = "end",
}: DialogProps) {
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  return (
    <DialogPrimitive.Root
      {...(open !== undefined ? { open } : {})}
      {...(onOpenChange ? { onOpenChange } : {})}
    >
      <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ds-overlay" />
        <DialogPrimitive.Content
          className={variant === "drawer" ? "ds-drawer" : "ds-dialog"}
          data-size={variant === "drawer" ? undefined : size}
          data-side={variant === "drawer" ? side : undefined}
          data-protected="" // issue 1: what a member confirms here is never restyled by an imported interface
        >
          <DialogPrimitive.Title>{title}</DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description>{description}</DialogPrimitive.Description>
          ) : (
            <DialogPrimitive.Description className="visually-hidden">{title}</DialogPrimitive.Description>
          )}
          <FooterSlot.Provider value={slot}>{children}</FooterSlot.Provider>
          <div className="ds-dialog__footer">
            <DialogPrimitive.Close asChild>
              <Button variant="secondary">{closeLabel}</Button>
            </DialogPrimitive.Close>
            {footer}
            <span className="ds-dialog__actions" ref={setSlot} />
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export function Drawer(props: Omit<DialogProps, "variant">) {
  return <Dialog {...props} variant="drawer" />;
}

export interface MenuItem {
  key: string;
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  /** Design-system icon name shown before the label (027). */
  icon?: string | undefined;
  /** Draw a separator before this item (027). */
  separated?: boolean;
}

export function Menu({
  trigger,
  items,
  label,
  header,
  align = "start",
}: {
  trigger: ReactNode;
  items: MenuItem[];
  label: string;
  /** Non-interactive content above the items (e.g. the signed-in user, 027). */
  header?: ReactNode;
  align?: "start" | "end";
}) {
  return (
    <MenuPrimitive.Root>
      <MenuPrimitive.Trigger asChild>{trigger}</MenuPrimitive.Trigger>
      <MenuPrimitive.Portal>
        <MenuPrimitive.Content className="ds-menu" aria-label={label} sideOffset={6} align={align}>
          {header ? <div className="ds-menu__header">{header}</div> : null}
          {items.map((item) => (
            <Fragment key={item.key}>
              {item.separated ? <MenuPrimitive.Separator className="ds-menu__separator" /> : null}
              <MenuPrimitive.Item
                className="ds-menu__item"
                disabled={item.disabled ?? false}
                onSelect={item.onSelect}
              >
                {item.icon ? <Icon name={item.icon} size={18} /> : null}
                {item.label}
              </MenuPrimitive.Item>
            </Fragment>
          ))}
        </MenuPrimitive.Content>
      </MenuPrimitive.Portal>
    </MenuPrimitive.Root>
  );
}

export function Popover({
  trigger,
  children,
  label,
}: {
  trigger: ReactNode;
  children: ReactNode;
  label: string;
}) {
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content className="ds-popover" aria-label={label} sideOffset={4}>
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

export function Tooltip({ children, content }: { children: ReactNode; content: string }) {
  return (
    <TooltipPrimitive.Provider delayDuration={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content className="ds-tooltip" sideOffset={4}>
            {content}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
