import { useMemo } from "react";
import type { CampaignOverlay } from "../../../design-system/themes/apply";
import { usePresentation } from "../api";

/**
 * Campaign theme overlay (spec 014 T024, R10): the server already applied the audience, priority, Admin
 * policy and the user's ``ui.campaignThemes`` choice; the 022 ``ThemeProvider`` then keeps accessibility
 * preferences (high contrast, floor checks) above it. Presentation never changes permissions or data.
 */
export function useCampaignOverlay(themes: readonly unknown[]): CampaignOverlay | null {
  const presentation = usePresentation();
  const theme = presentation.data?.theme;
  return useMemo(() => {
    if (!theme) return null;
    const definition = themes.find(
      (candidate) => (candidate as { key?: string } | null)?.key === theme.theme_key,
    ) as { colors?: CampaignOverlay["colors"] } | undefined;
    if (!definition?.colors) return null;
    return { key: theme.campaign ?? theme.theme_key ?? "campaign", colors: definition.colors };
  }, [theme, themes]);
}
