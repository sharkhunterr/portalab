import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

/** Button (WCAG 2.2: target ≥ 24×24, visible focus from tokens, real ``<button>`` semantics). */
const button = cva("ds-button", {
  variants: {
    variant: {
      primary: "ds-button--primary",
      secondary: "ds-button--secondary",
      danger: "ds-button--danger",
    },
  },
  defaultVariants: { variant: "primary" },
});

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  asChild?: boolean;
}

export function Button({ asChild = false, variant, className, type, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      className={button({ variant, className })}
      type={asChild ? undefined : (type ?? "button")}
      {...props}
    />
  );
}

export interface LinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  children: ReactNode;
  external?: boolean;
}

/** Link: underlined (not color-only); external links announce that they open elsewhere. */
export function Link({ external = false, children, className, ...props }: LinkProps) {
  return (
    <a
      className={["ds-link", className].filter(Boolean).join(" ")}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      {...props}
    >
      {children}
      {external ? <span className="visually-hidden"> (opens in a new tab)</span> : null}
    </a>
  );
}
