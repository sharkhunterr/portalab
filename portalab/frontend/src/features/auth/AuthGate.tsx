import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import { AuthLayout } from "../../design-system/components/AuthLayout";
import { FunctionalState } from "../../design-system/FunctionalState";
import { PortalUnreachable } from "../../shell/router/PortalUnreachable";
import { inLanguage, useSite } from "../../shell/site/site";
import { ApiError, stateForError } from "../../state/regions";
import { ArrivalWizard } from "../admin/arrival/ArrivalWizard";
import { Resetting } from "../admin/arrival/Resetting";
import { LoginForm } from "./LoginForm";
import { useAuthStrings } from "./strings";
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
  const t = useAuthStrings();
  const me = useMe();
  const arrival = useArrivalOpen(me.isSuccess && !me.data);
  // issue 159: the site's name, logo and slogan (in the browser's language, else the default one)
  const site = useSite();
  const tagline = inLanguage(site.tagline, globalThis.navigator?.language ?? "en") ?? t.tagline;
  const layout = { brand: site.name, logo: site.logo, tagline };
  // issue 246: a portal nobody has set up yet shows its arrival wizard, whatever the address
  if (location?.pathname === "/resetting") return <Resetting />; // issue 247: the session goes with the data
  if (location?.pathname === "/setup" || (me.isSuccess && !me.data && arrival.data)) return <ArrivalWizard />;
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

/** Whether the portal still waits for its first administrator (asked only by a visitor without a session). */
function useArrivalOpen(anonymous: boolean) {
  return useQuery({
    queryKey: ["admin", "first-run", "open"],
    enabled: anonymous,
    retry: false,
    staleTime: 60_000,
    queryFn: async () => {
      try {
        const data = (await api.GET("/api/v1/admin/first-run")).data as unknown as { completed?: boolean };
        return data?.completed === false;
      } catch {
        return false; // set up: the very same answer as any address
      }
    },
  });
}

export function SignOutButton() {
  const t = useAuthStrings();
  const logout = useLogout();
  return (
    <button type="button" onClick={() => logout.mutate()} disabled={logout.isPending}>
      {t.signOut}
    </button>
  );
}
