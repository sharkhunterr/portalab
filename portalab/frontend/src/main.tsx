import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AccountPage, AuthGate, SignOutButton } from "./features/auth";
import { AppShell } from "./shell/AppShell";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
});

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
          </AppShell>
        )}
      </AuthGate>
    </QueryClientProvider>
  </StrictMode>,
);
