import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AnnounceProvider } from "./design-system/a11y/Announce";
import { DirectionProvider } from "./design-system/rtl/DirectionProvider";
import { applyFirstPaint } from "./design-system/themes/firstPaint";
import {
  ConfigEditor,
  ControlCenter,
  EventsAdmin,
  ObservabilityAdmin,
  ServicesAdmin,
  Toggles,
} from "./features/admin";
import { AppearanceRoot, AppearanceSettings } from "./features/appearance";
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

applyFirstPaint();

async function renderGallery(): Promise<boolean> {
  if (!import.meta.env.DEV || window.location.pathname !== "/dev/gallery") return false;
  const { Gallery } = await import("./features/dev/gallery/Gallery");
  createRoot(container as HTMLElement).render(
    <StrictMode>
      <Gallery />
    </StrictMode>,
  );
  return true;
}

void renderGallery().then((gallery) => {
  if (gallery) return;
  createRoot(container as HTMLElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <DirectionProvider language="en">
          <AnnounceProvider>
            <AuthGate>
              {() => (
                <AppearanceRoot>
                  <AppShell navigation={<SignOutButton />}>
                    <AccountPage />
                    <AppearanceSettings />
                    <PrivacyCenter />
                    <ServicesSection />
                    <AdminSections />
                  </AppShell>
                </AppearanceRoot>
              )}
            </AuthGate>
          </AnnounceProvider>
        </DirectionProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
});
