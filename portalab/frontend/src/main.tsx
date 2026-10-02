import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  ConfigEditor,
  ControlCenter,
  EventsAdmin,
  ObservabilityAdmin,
  ServicesAdmin,
  Toggles,
} from "./features/admin";
import { AccountPage, AuthGate, SignOutButton } from "./features/auth";
import { AuthzAdminPage, useHasPermission } from "./features/authz";
import { AuditViewer, PoliciesAdmin, PrivacyCenter } from "./features/privacy";
import { ServicesHealth } from "./features/services";
import { AppShell } from "./shell/AppShell";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
});

function AdminSections() {
  const roles = useHasPermission("users.roles.manage");
  const privacy = useHasPermission("privacy.manage");
  const audit = useHasPermission("audit.read");
  const configuration = useHasPermission("configuration.manage");
  const events = useHasPermission("events.manage");
  const services = useHasPermission("services.manage");
  const observability = useHasPermission("observability.read");
  return (
    <>
      <ControlCenter />
      {configuration ? <ConfigEditor /> : null}
      {configuration ? <Toggles /> : null}
      {events ? <EventsAdmin /> : null}
      {services ? <ServicesAdmin /> : null}
      {observability ? <ObservabilityAdmin /> : null}
      {roles ? <AuthzAdminPage /> : null}
      {privacy ? <PoliciesAdmin /> : null}
      {audit ? <AuditViewer /> : null}
    </>
  );
}

function ServicesSection() {
  return useHasPermission("services.read") ? <ServicesHealth /> : null;
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
            <ServicesSection />
            <AdminSections />
          </AppShell>
        )}
      </AuthGate>
    </QueryClientProvider>
  </StrictMode>,
);
