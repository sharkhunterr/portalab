import type { ReactNode } from "react";
import { Icon } from "./Icon";

/**
 * Screens before sign-in (spec 027 FR-028, R22): a branded, centered card over the theme's ambient
 * background — sign-in, verification, recovery, first run. Comfortable from 320 px to desktop.
 */
export function AuthLayout({
  brand = "Portalab",
  logo,
  tagline,
  children,
}: {
  brand?: string;
  /** issue 159: the site's logo, in place of the mark */
  logo?: string | null | undefined;
  tagline?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div className="ds-auth">
      <div className="ds-auth__card">
        <div className="ds-auth__brand">
          {logo ? (
            <img className="ds-auth__logo" src={logo} alt="" />
          ) : (
            <span className="ds-auth__mark" aria-hidden="true">
              <Icon name="sparkles" size={26} />
            </span>
          )}
          <span className="ds-auth__name">{brand}</span>
        </div>
        {tagline ? <p className="ds-auth__tagline">{tagline}</p> : null}
        {children}
      </div>
    </div>
  );
}
