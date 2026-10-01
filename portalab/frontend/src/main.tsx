import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { FunctionalState } from "./design-system/FunctionalState";
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
      <AppShell>
        <h1 className="text-xl font-semibold">Portalab</h1>
        <FunctionalState state="no-data" detail="The portal foundation is running." />
      </AppShell>
    </QueryClientProvider>
  </StrictMode>,
);
