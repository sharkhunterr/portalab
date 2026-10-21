import type { ReactNode } from "react";
import { AuthLayout } from "../../design-system/components/AuthLayout";
import { FunctionalState } from "../../design-system/FunctionalState";
import { PortalUnreachable } from "../../shell/router/PortalUnreachable";
import { inLanguage, useSite } from "../../shell/site/site";
import { ApiError, stateForError } from "../../state/regions";
import { FirstRunWizard } from "../admin/FirstRunWizard";
import { LoginForm } from "./LoginForm";
import { authStrings as t } from "./strings";
import { type Me, useLogout, useMe } from "./useAuth";
import { VerifyForm } from "./VerifyForm";

/**
 * Shows the sign-in (or activation) screen to anonymous visitors and the portal to signed-in users. This is
 * a UI convenience only: every API route is still authorized server-side (deny by default).
 */
export function AuthGate({
  children,
  location = globalThis.location,
}: {
  children: (me: Me) => ReactNode;
  location?: Pick<Location, "pathname" | "search">;
}) {
  const me = useMe();
  // issue 159: the site's name, logo and slogan (in the browser's language, else the default one)
  const site = useSite();
  const tagline = inLanguage(site.tagline, globalThis.navigator?.language ?? "en") ?? t.tagline;
  const layout = { brand: site.name, logo: site.logo, tagline };
  if (location?.pathname === "/setup") return <FirstRunWizard />;
  if (location?.pathname === "/verify") {
    const token = new URLSearchParams(location.search).get("token") ?? "";
    return (
      <AuthLayout {...layout}>
        <VerifyForm initialToken={token} />
      </AuthLayout>
    );
  }
  if (me.isPending) return <FunctionalState state="loading" detail={t.loginTitle} />;
  if (me.isError) {
    // issue 16: the portal does not answer (no reply, or a server error) — its own page, trying again
    const status = me.error instanceof ApiError ? me.error.status : 0;
    if (!status || status >= 500) return <PortalUnreachable />;
    return <FunctionalState state={stateForError(me.error)} onRetry={() => void me.refetch()} />;
  }
  if (!me.data)
    return (
      <AuthLayout {...layout}>
        <LoginForm />
      </AuthLayout>
    );
  return <>{children(me.data)}</>;
}

export function SignOutButton() {
  const logout = useLogout();
  return (
    <button type="button" onClick={() => logout.mutate()} disabled={logout.isPending}>
      {t.signOut}
    </button>
  );
}
