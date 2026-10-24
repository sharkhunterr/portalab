import { useShellPreference } from "../../shell/preferences";

/** Issue 243: the welcome's « do you want to play? » answers that leave the cards out (the server gives
 * no card booster then either); the other boosters, the progression and the shop stay. */
const WITHOUT_CARDS = new Set(["progression", "none"]);

/** Whether the member collects the Mediacards — the cards' pages, boosters and sections shown or not. */
export function useCollectsCards(): boolean {
  const [play] = useShellPreference<string | null>("shell.onboarding.play", null);
  return !WITHOUT_CARDS.has(play ?? "");
}
