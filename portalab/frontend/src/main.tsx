import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { AnnounceProvider } from "./design-system/a11y/Announce";
import { DirectionProvider } from "./design-system/rtl/DirectionProvider";
import { applyFirstPaint } from "./design-system/themes/firstPaint";
import { AppearanceRoot } from "./features/appearance";
import { AuthGate } from "./features/auth";
import { NavigationProvider } from "./shell/nav/NavigationProvider";
import { createRouter } from "./shell/router/routes";
import { ShellLayout } from "./shell/ShellLayout";
import "./styles.css";

/**
 * Entry point: first paint from mirrored preferences, then the sign-in gate (anonymous visitors never see
 * the shell, CD-025), then the persistent shell with the lazily loaded routes (spec 004).
 */
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
});

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

const router = createRouter(<ShellLayout />);

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
                  <NavigationProvider>
                    <RouterProvider router={router} />
                  </NavigationProvider>
                </AppearanceRoot>
              )}
            </AuthGate>
          </AnnounceProvider>
        </DirectionProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
});
