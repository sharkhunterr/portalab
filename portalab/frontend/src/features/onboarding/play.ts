import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { NAVIGATION_KEY } from "../../shell/nav/NavigationProvider";
import { useShellPreference } from "../../shell/preferences";
import { setPresence } from "../auth/CommunityPresence";

/** Whether the member plays (``shell.onboarding.play``): a player is public, within the portal only; the
 * others are anonymous, seen by no other member. Without the cards (issue 243), the Mediacards are hidden.
 * Issue 347: a gauge from no game to all of it — each notch adds to the one below (``from``: what it adds). */
export const PLAY = [
  { key: "none", icon: "hide", level: "private" },
  { key: "progression", icon: "trophy", level: "community" },
  { key: "collector", icon: "layers", level: "community" },
  { key: "full", icon: "game", level: "community" },
] as const;
export type Play = (typeof PLAY)[number]["key"];

/** Issue 347: what the gauge brings, and from which notch on. */
export const PLAY_FEATURES = [
  { key: "media", icon: "film", from: "none" },
  { key: "progression", icon: "trophy", from: "progression" },
  { key: "quests", icon: "target", from: "progression" },
  { key: "cards", icon: "layers", from: "collector" },
  { key: "games", icon: "game", from: "full" },
] as const satisfies ReadonlyArray<{ key: string; icon: string; from: Play }>;

export const playIndex = (play: Play) => PLAY.findIndex((choice) => choice.key === play);

/** The answer kept, and its saving: the profile's presence follows it, the menu shows the cards or not. Asked
 * at the welcome and changed in the settings (« Play », issue 14). */
export function usePlay(onSaved?: () => void) {
  const client = useQueryClient();
  const [saved, setSaved] = useShellPreference<Play | null>("shell.onboarding.play", null);
  const save = useMutation({
    mutationFn: async (play: Play) => {
      await setPresence(PLAY.find((choice) => choice.key === play)?.level ?? "community");
      // issue 347: kept before anything follows it (the profile's dashboard reads it)
      await api.PUT("/api/v1/me/preferences", { body: { "shell.onboarding.play": play } as never });
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

/** Issue 347: what a member may want on their home — each brings its widgets (the server knows which). */
export const TASTES = [
  { key: "watch", icon: "play" },
  { key: "releases", icon: "calendar" },
  { key: "news", icon: "rss" },
  { key: "requests", icon: "inbox" },
  { key: "play", icon: "gamepad" },
  { key: "stats", icon: "chart" },
  { key: "services", icon: "server" },
  { key: "community", icon: "users" },
  { key: "radio", icon: "radio" },
] as const;

/** The tastes ticked at first: the media, the news and the services, and the game for a player. */
export const tastesFor = (play: Play) =>
  TASTES.map((taste) => taste.key).filter(
    (key) =>
      ["watch", "releases", "news", "requests", "services"].includes(key) ||
      (key === "play" && play !== "none"),
  );

/** Issue 347: the dashboard the administrator prepared for the member's play profile — their own arrangement
 * is replaced by it. */
export function useProfileDashboard() {
  const client = useQueryClient();
  return useMutation({
    // issue 347: made to the member's tastes when they are given (the welcome's « your portal to your taste »)
    mutationFn: async (tastes?: readonly string[]) => {
      await api.POST("/api/v1/dashboard/reset", tastes ? { body: { tastes: [...tastes] } as never } : {});
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["dashboard"] }),
  });
}
