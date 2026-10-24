import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NAVIGATION_KEY } from "../../shell/nav/NavigationProvider";
import { useShellPreference } from "../../shell/preferences";
import { setPresence } from "../auth/CommunityPresence";

/** Whether the member plays (``shell.onboarding.play``): a player is public, within the portal only; the
 * others are anonymous, seen by no other member. Without the cards (issue 243), the Mediacards are hidden. */
export const PLAY = [
  { key: "full", icon: "layers", level: "community" },
  { key: "progression", icon: "trophy", level: "community" },
  { key: "none", icon: "hide", level: "private" },
] as const;
export type Play = (typeof PLAY)[number]["key"];

/** The answer kept, and its saving: the profile's presence follows it, the menu shows the cards or not. Asked
 * at the welcome and changed in the settings (« Play », issue 14). */
export function usePlay(onSaved?: () => void) {
  const client = useQueryClient();
  const [saved, setSaved] = useShellPreference<Play | null>("shell.onboarding.play", null);
  const save = useMutation({
    mutationFn: async (play: Play) => {
      await setPresence(PLAY.find((choice) => choice.key === play)?.level ?? "community");
    },
    onSuccess: async (_, play) => {
      setSaved(play);
      await client.invalidateQueries({ queryKey: NAVIGATION_KEY }); // issue 243: the cards, or not, in the menu
      await client.invalidateQueries({ queryKey: ["privacy", "me"] });
      await client.invalidateQueries({ queryKey: ["community"] });
      onSaved?.();
    },
  });
  return { saved, save };
}
