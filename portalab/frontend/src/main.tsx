import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AccountPage, AuthGate, SignOutButton } from "./features/auth";
import { AuthzAdminPage, useHasPermission } from "./features/authz";
import { AuditViewer, PoliciesAdmin, PrivacyCenter } from "./features/privacy";
import { AppShell } from "./shell/AppShell";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
});

function AdminSections() {
  const roles = useHasPermission("users.roles.manage");
  const privacy = useHasPermission("privacy.manage");
  const audit = useHasPermission("audit.read");
  return (
    <>
      {roles ? <AuthzAdminPage /> : null}
      {privacy ? <PoliciesAdmin /> : null}
      {audit ? <AuditViewer /> : null}
    </>
  );
}

const container = document.getElementById("root");
if (!container) {
  throw new Error("missing #root element");
}

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthGate>
        {() => (
          <AppShell navigation={<SignOutButton />}>
            <AccountPage />
            <PrivacyCenter />
            <AdminSections />
          </AppShell>
        )}
      </AuthGate>
    </QueryClientProvider>
  </StrictMode>,
);
