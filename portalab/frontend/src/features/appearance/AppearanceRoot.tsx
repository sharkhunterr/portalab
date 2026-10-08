import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useContext, useMemo } from "react";
import { IntlContext } from "react-intl";
import { api } from "../../api/client";
import { PreferencesProvider } from "../../design-system/a11y/PreferencesProvider";
import { NotificationArea } from "../../design-system/components/Notification";
import { CelebrationProvider } from "../../design-system/feedback/Celebration";
import { AmbientLayer } from "../../design-system/themes/AmbientLayer";
import type { LockedLooks } from "../../design-system/themes/apply";
import { ThemeProvider, useTheme } from "../../design-system/themes/ThemeProvider";
import { VocabularyContext } from "../../i18n";
import { useCampaignOverlay } from "../campaigns/presentation/CampaignPresentationProvider";
import { preferenceBackend } from "./backend";

/** 027: the active theme's words for the active language, and its animated ambient layer. */
function ThemeUniverse({ children }: { children: ReactNode }) {
  const { effective, looks } = useTheme();
  const intl = useContext(IntlContext);
  const language = intl?.locale.split("-")[0] ?? "en";
  const terms = effective.theme.vocabulary;
  const vocabulary = useMemo(() => terms?.[language] ?? terms?.en ?? {}, [terms, language]);
  return (
    <VocabularyContext.Provider value={vocabulary}>
      <AmbientLayer kind={looks.ambient} />
      {children}
    </VocabularyContext.Provider>
  );
}

interface LooksCatalog {
  styles?: Array<{ key: string; locked: boolean }>;
  animations?: Array<{ key: string; locked: boolean }>;
  ambients?: Array<{ key: string; locked: boolean }>;
  celebrations?: Array<{ key: string; locked: boolean }>;
  level_ups?: Array<{ key: string; locked: boolean }>;
}

/**
 * 027: what the member may not wear. A universe theme alone brings its colours, layout and words; its sold
 * looks (ambience, notifications, celebration, level-up) come with the universe's pack. While the
 * catalog loads they wait (``null``); if it cannot be read, nothing is withheld.
 */
function useLockedLooks(): LockedLooks | null | undefined {
  const catalog = useQuery({
    queryKey: ["ui", "notification-looks"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/ui/notification-looks")).data as unknown as LooksCatalog,
  });
  return useMemo(() => {
    if (catalog.isError) return undefined;
    if (!catalog.data) return null;
    const set = (list?: Array<{ key: string; locked: boolean }>) =>
      new Set((list ?? []).filter((c) => c.locked).map((c) => c.key));
    return {
      notificationStyle: set(catalog.data.styles),
      notificationAnimation: set(catalog.data.animations),
      ambient: set(catalog.data.ambients),
      celebration: set(catalog.data.celebrations),
      levelUp: set(catalog.data.level_ups),
    };
  }, [catalog.data, catalog.isError]);
}

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
  const lockedLooks = useLockedLooks();
  return (
    <ThemeProvider themes={catalog.data ?? []} overlay={overlay} lockedLooks={lockedLooks}>
      <ThemeUniverse>
        <NotificationArea>
          <CelebrationProvider>{children}</CelebrationProvider>
        </NotificationArea>
      </ThemeUniverse>
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
