import { useLogout, useMe } from "../features/auth/useAuth";
import { NotificationSlot } from "../features/notifications/bell/NotificationSlot";
import { AppShell } from "./AppShell";

/** The shell as the router's root element, fed by the signed-in account. */
export function ShellLayout() {
  const me = useMe();
  const logout = useLogout();
  return (
    <NotificationSlot>
      <AppShell userName={me.data?.display_name ?? me.data?.login ?? ""} onSignOut={() => logout.mutate()} />
    </NotificationSlot>
  );
}
