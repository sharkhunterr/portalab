import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

/**
 * Member onboarding (#7): the portal's welcome (on/off and the admin's own words), the steps done
 * (``/me/onboarding``) and the « first steps » missions — discovery quests, each rewarded once.
 */
export interface Welcome {
  enabled: boolean;
  message: string;
}

export interface Mission {
  key: string;
  kind: string;
  label: string;
  icon?: string | null;
  completed_at: string | null;
  rewards: Array<{ value: string; amount?: number | null }>;
  steps: Array<{ current: number; target: number }>;
}

/** Fired to (re)start the guided tour from anywhere (menu, missions, end of the welcome). */
export const TOUR_EVENT = "portalab:tour";
/** Fired to reopen the welcome from the personal menu. */
export const WELCOME_EVENT = "portalab:welcome";

/** Starts a guided tour (``tours.ts``); the portal's own tour by default. */
export function startTour(tour = "portal"): void {
  window.dispatchEvent(new CustomEvent(TOUR_EVENT, { detail: tour }));
}

export function openWelcome(): void {
  window.dispatchEvent(new CustomEvent(WELCOME_EVENT));
}

export function useWelcome() {
  return useQuery({
    queryKey: ["onboarding", "welcome"],
    staleTime: 10 * 60_000,
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/me/onboarding/welcome")).data as Welcome,
  });
}

export async function completeStep(step: string): Promise<void> {
  await api.POST("/api/v1/me/onboarding/{step}/complete", { params: { path: { step } } });
}

export async function completeTour(tour: string): Promise<void> {
  await api.POST("/api/v1/me/onboarding/tours/{tour}/complete", { params: { path: { tour } } });
}

export const MISSIONS_KEY = ["onboarding", "missions"] as const;

export function useMissions(enabled = true) {
  return useQuery({
    queryKey: MISSIONS_KEY,
    enabled,
    retry: false,
    staleTime: 30_000,
    queryFn: async () =>
      (((await api.GET("/api/v1/me/quests")).data ?? []) as unknown as Mission[]).filter(
        (quest) => quest.kind === "discovery",
      ),
  });
}

export function rewardOf(mission: Mission): { xp: number; coins: number } {
  let xp = 0;
  let coins = 0;
  for (const reward of mission.rewards) {
    if (reward.value === "xp") xp += reward.amount ?? 0;
    if (reward.value === "coins") coins += reward.amount ?? 0;
  }
  return { xp, coins };
}
