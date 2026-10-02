import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as MenuPrimitive from "@radix-ui/react-dropdown-menu";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";
import { Button } from "./Button";

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
}: DialogProps) {
  return (
    <DialogPrimitive.Root
      {...(open !== undefined ? { open } : {})}
      {...(onOpenChange ? { onOpenChange } : {})}
    >
      <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ds-overlay" />
        <DialogPrimitive.Content className={variant === "drawer" ? "ds-drawer" : "ds-dialog"}>
          <DialogPrimitive.Title>{title}</DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description>{description}</DialogPrimitive.Description>
          ) : (
            <DialogPrimitive.Description className="visually-hidden">{title}</DialogPrimitive.Description>
          )}
          {children}
          <DialogPrimitive.Close asChild>
            <Button variant="secondary">{closeLabel}</Button>
          </DialogPrimitive.Close>
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
}

export function Menu({ trigger, items, label }: { trigger: ReactNode; items: MenuItem[]; label: string }) {
  return (
    <MenuPrimitive.Root>
      <MenuPrimitive.Trigger asChild>{trigger}</MenuPrimitive.Trigger>
      <MenuPrimitive.Portal>
        <MenuPrimitive.Content className="ds-menu" aria-label={label} sideOffset={4}>
          {items.map((item) => (
            <MenuPrimitive.Item
              key={item.key}
              className="ds-menu__item"
              disabled={item.disabled ?? false}
              onSelect={item.onSelect}
            >
              {item.label}
            </MenuPrimitive.Item>
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
