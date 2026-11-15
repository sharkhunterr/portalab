import type { ReactNode } from "react";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { StatusPage } from "../../design-system/components/StatusPage";
import { useT } from "../../i18n/hooks/useT";
import { rememberedSite, useSite } from "../site/site";

/**
 * Issue 448: the portal's pages between pages, in one look ({@link StatusPage}) — loading, a page this
 * account may not open, a page that is not there, one that failed, a service away. Full page outside the
 * portal's frame, or ``inline`` in its content area.
 */
export type RouteState = "unauthorized" | "not-available" | "not-found" | "unavailable" | "error";

/** The site's name and logo — the last known ones while the portal is away. */
export function useSiteBrand(): { brand: string; logo: string | null } {
  const live = useSite();
  const remembered = live.custom ? null : rememberedSite();
  return { brand: remembered?.name ?? live.name, logo: live.logo ?? remembered?.icon ?? null };
}

/** The words, else these English ones (the catalogs may not be there: the portal starting, or away). */
function useSay() {
  const t = useT();
  return (key: string, fallback: string) => {
    const text = t(key);
    return text === key || text === key.split(":")[1] ? fallback : text;
  };
}

export function LoadingPage({ inline = false }: { inline?: boolean }) {
  return inline ? <Loading /> : <Branded render={(site) => <Loading {...site} />} />;
}

function Loading({ brand, logo }: { brand?: string; logo?: string | null }) {
  const say = useSay();
  return (
    <StatusPage
      kind="loading"
      icon="sparkles"
      busy
      inline={!brand}
      brand={brand}
      logo={logo}
      title={say("shell:status.loading", "Loading…")}
    />
  );
}

/** The site's name and logo for a full page (within the portal's frame, the header says it). */
function Branded({ render }: { render: (site: { brand: string; logo: string | null }) => ReactNode }) {
  const site = useSiteBrand();
  return <>{render(site)}</>;
}

/** Home, and the page before when there is one (a page opened from a link has none). */
function Ways({ retry }: { retry?: (() => void) | undefined }) {
  const say = useSay();
  // outside the router too (the sign-in gate): the browser's own history
  const before = typeof window !== "undefined" && window.history.length > 1;
  return (
    <>
      {retry ? (
        <Button onClick={retry}>
          <Icon name="retry" size={16} />
          {say("shell:retry", "Retry")}
        </Button>
      ) : null}
      <a className={`ds-button ${retry ? "ds-button--secondary" : "ds-button--primary"}`} href="/">
        <Icon name="home" size={16} />
        {say("shell:status.home", "Back to the home page")}
      </a>
      {before ? (
        <Button variant="ghost" onClick={() => window.history.back()}>
          <Icon name="chevron-left" size={16} />
          {say("shell:status.back", "Previous page")}
        </Button>
      ) : null}
    </>
  );
}

export function RouteStateView({
  state,
  onRetry,
  inline = false,
}: {
  state: RouteState;
  onRetry?: (() => void) | undefined;
  inline?: boolean;
}) {
  if (inline) return <StateBody state={state} onRetry={onRetry} inline />;
  return <Branded render={(site) => <StateBody state={state} onRetry={onRetry} {...site} />} />;
}

function StateBody({
  state,
  onRetry,
  inline = false,
  brand,
  logo,
}: {
  state: RouteState;
  onRetry?: (() => void) | undefined;
  inline?: boolean;
  brand?: string;
  logo?: string | null;
}) {
  const say = useSay();
  const frame = { inline, brand, logo, kind: state };
  if (state === "not-available" || state === "not-found")
    return (
      <StatusPage
        {...frame}
        icon="compass"
        title={say("shell:status.notFound.title", "This page is not here")}
        text={
          state === "not-found"
            ? say("shell:status.notFound.text", "The address may be wrong, or the page moved or was removed.")
            : say("shell:notAvailableDetail", "It may not exist, or you may not have access to it.")
        }
      >
        <Ways />
      </StatusPage>
    );
  if (state === "unauthorized")
    return (
      <StatusPage
        {...frame}
        icon="lock"
        tone="warning"
        title={say("shell:status.forbidden.title", "This page is not open to you")}
        text={say(
          "shell:status.forbidden.text",
          "Your account may not open it. On a household profile, it may be your master's.",
        )}
      >
        <Ways />
      </StatusPage>
    );
  if (state === "unavailable")
    return (
      <StatusPage
        {...frame}
        icon="server"
        pulse
        title={say("shell:status.unavailable.title", "This service is away for a moment")}
        text={say("shell:status.unavailable.text", "It may be restarting. Try again in a moment.")}
      >
        <Ways retry={onRetry} />
      </StatusPage>
    );
  return (
    <StatusPage
      {...frame}
      icon="alert"
      tone="danger"
      alert
      title={say("shell:status.error.title", "This page could not be loaded")}
      text={say("shell:status.error.text", "Something went wrong on the way. Try again, or come back later.")}
    >
      <Ways retry={onRetry} />
    </StatusPage>
  );
}
