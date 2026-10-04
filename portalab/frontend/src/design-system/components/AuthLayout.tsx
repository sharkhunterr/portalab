import type { ReactNode } from "react";
import { Icon } from "./Icon";

/**
 * Screens before sign-in (spec 027 FR-028, R22): a branded, centered card over the theme's ambient
 * background — sign-in, verification, recovery, first run. Comfortable from 320 px to desktop.
 */
export function AuthLayout({
  brand = "Portalab",
  tagline,
  children,
}: {
  brand?: string;
  tagline?: string;
  children: ReactNode;
}) {
  return (
    <div className="ds-auth">
      <div className="ds-auth__card">
        <div className="ds-auth__brand">
          <span className="ds-auth__mark" aria-hidden="true">
            <Icon name="sparkles" size={26} />
          </span>
          <span className="ds-auth__name">{brand}</span>
        </div>
        {tagline ? <p className="ds-auth__tagline">{tagline}</p> : null}
        {children}
      </div>
    </div>
  );
}
