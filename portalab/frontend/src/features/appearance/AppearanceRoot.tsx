import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import { PreferencesProvider } from "../../design-system/a11y/PreferencesProvider";
import { NotificationArea } from "../../design-system/components/Notification";
import { CelebrationProvider } from "../../design-system/feedback/Celebration";
import { ThemeProvider } from "../../design-system/themes/ThemeProvider";
import { useCampaignOverlay } from "../campaigns/presentation/CampaignPresentationProvider";
import { preferenceBackend } from "./backend";

/** Signed-in presentation root: account preferences (synced), the allowed theme catalog, notifications. */
function Themed({ children }: { children: ReactNode }) {
  const catalog = useQuery({
    queryKey: ["ui", "themes"],
    queryFn: async () =>
      (
        (await api.GET("/api/v1/ui/themes")).data as unknown as { themes: Array<{ definition: unknown }> }
      ).themes.map((t) => t.definition),
    staleTime: 5 * 60_000,
  });
  const overlay = useCampaignOverlay(catalog.data ?? []); // 014 campaign theme, 022 keeps a11y above it
  return (
    <ThemeProvider themes={catalog.data ?? []} overlay={overlay}>
      <NotificationArea>
        <CelebrationProvider>{children}</CelebrationProvider>
      </NotificationArea>
    </ThemeProvider>
  );
}

export function AppearanceRoot({ children }: { children: ReactNode }) {
  return (
    <PreferencesProvider backend={preferenceBackend}>
      <Themed>{children}</Themed>
    </PreferencesProvider>
  );
}
