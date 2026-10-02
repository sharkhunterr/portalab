import type { ReactNode } from "react";
import { FunctionalState } from "../../design-system/FunctionalState";
import { stateForError } from "../../state/regions";
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
  if (location?.pathname === "/setup") return <FirstRunWizard />;
  if (location?.pathname === "/verify") {
    const token = new URLSearchParams(location.search).get("token") ?? "";
    return <VerifyForm initialToken={token} />;
  }
  if (me.isPending) return <FunctionalState state="loading" detail={t.loginTitle} />;
  if (me.isError)
    return <FunctionalState state={stateForError(me.error)} onRetry={() => void me.refetch()} />;
  if (!me.data) return <LoginForm />;
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
