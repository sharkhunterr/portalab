import type { ReactNode } from "react";
import { Icon } from "./Icon";

/**
 * Issue 448: the pages between pages — the portal away, a page one may not open, a page that is not there,
 * one that failed, the portal loading — one look, the sign-in's: the site's name and logo, a picture of what
 * is happening, a title, a few words, what to do next. Full page outside the portal's frame (``inline``
 * false), or within its content area (the menu and the header stay).
 */
export function StatusPage({
  icon,
  title,
  text,
  children,
  brand,
  logo,
  inline = false,
  pulse = false,
  busy = false,
  tone = "accent",
  alert = false,
  kind,
}: {
  icon: string;
  title: ReactNode;
  text?: ReactNode;
  /** What to do next (buttons, links) — or a countdown. */
  children?: ReactNode;
  /** The site's name (full page only). */
  brand?: string | undefined;
  logo?: string | null | undefined;
  inline?: boolean;
  /** A slow ring around the picture: something is under way (the portal tried again, loading). */
  pulse?: boolean;
  busy?: boolean;
  tone?: "accent" | "warning" | "danger";
  /** Said at once to screen readers (an error); else politely. */
  alert?: boolean;
  /** What it says (``data-state``: loading, unauthorized, not-found…), for themes and tests. */
  kind?: string;
}) {
  const Frame = inline ? "div" : "main";
  const Heading = inline ? "h2" : "h1";
  return (
    <Frame
      className={`ds-status${inline ? " ds-status--inline" : ""}`}
      role={alert ? "alert" : "status"}
      aria-live={alert ? "assertive" : "polite"}
      aria-busy={busy || undefined}
      data-state={kind}
    >
      <div className="ds-status__card">
        {brand && !inline ? (
          <p className="ds-status__brand">
            {logo ? (
              <img className="ds-status__logo" src={logo} alt="" />
            ) : (
              <span className="ds-status__mark" aria-hidden="true">
                <Icon name="sparkles" size={18} />
              </span>
            )}
            {brand}
          </p>
        ) : null}
        <span className="ds-status__art" data-tone={tone} aria-hidden="true">
          <Icon name={icon} size={inline ? 32 : 40} />
          {pulse || busy ? <span className="ds-status__pulse" /> : null}
        </span>
        <Heading className="ds-status__title">{title}</Heading>
        {text ? <p className="ds-status__text">{text}</p> : null}
        {children ? <div className="ds-status__actions">{children}</div> : null}
      </div>
    </Frame>
  );
}
