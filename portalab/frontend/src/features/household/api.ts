import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { NAVIGATION_KEY } from "../../shell/nav/NavigationProvider";

/**
 * Households (spec 032): the « Who's there? » picker and the switch, the household page (every member sees
 * it), its management and the access requests (the master decides).
 */
export type HouseholdSession = components["schemas"]["HouseholdSession"];
export type MemberTile = components["schemas"]["HouseholdMemberTile"];
export type Household = components["schemas"]["HouseholdOut"];
export type HouseholdMember = components["schemas"]["HouseholdMemberOut"];
export type RestrictionSettings = components["schemas"]["RestrictionSettings"];
export type AccessRequest = components["schemas"]["AccessRequestOut"];
export type ProfileActivity = components["schemas"]["ProfileActivityOut"];
export type ProfileKind = "standard" | "child" | "custom";

export const SESSION_KEY = ["household", "session"] as const;
export const HOUSEHOLD_KEY = ["household", "overview"] as const;
export const REQUESTS_KEY = ["household", "requests"] as const;
/** Opens the picker from anywhere (the header's « Switch profile »). */
export const CHOOSE_PROFILE_EVENT = "portalab:choose-profile";
export const AGES = [0, 6, 10, 12, 14, 16, 18] as const;
export const FEATURES = ["shop", "requests", "ai", "community", "games", "support"] as const;
export const GENRES = ["horror", "thriller", "crime", "war"] as const; // 032: kept out whatever their rating
export const TYPES = ["movies", "series", "books", "audiobooks", "music", "games"] as const;
export const SCREEN_MINUTES = [15, 30, 45, 60, 90, 120, 180, 240, 300] as const;

/** Opens the picker — on one member's PIN pad when ``member`` is given. */
export function chooseProfile(member?: string) {
  globalThis.dispatchEvent?.(new CustomEvent(CHOOSE_PROFILE_EVENT, { detail: member ?? null }));
}

export function useHouseholdSession(enabled = true) {
  return useQuery({
    queryKey: SESSION_KEY,
    enabled,
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/household/session")).data as HouseholdSession,
  });
}

/** Acting as another household member: the whole portal reloads as them (nothing of the previous one stays). */
export function useSwitchProfile() {
  return useMutation({
    mutationFn: async (body: { user_id: string; pin?: string | undefined; next?: string | undefined }) => {
      await api.POST("/api/v1/household/switch", {
        body: { user_id: body.user_id, ...(body.pin ? { pin: body.pin } : {}) },
      });
      return body.next ?? "/";
    },
    onSuccess: (to) => globalThis.location?.assign(to),
  });
}

export function useHousehold(enabled = true) {
  return useQuery({
    queryKey: HOUSEHOLD_KEY,
    enabled,
    queryFn: async () => (await api.GET("/api/v1/household")).data as Household,
  });
}

export type RatingPolicy = components["schemas"]["RatingPolicyOut"];

/** Issue 478: how the portal reads a title's age (its administrator's policy) — « as the portal » told. */
export function useRatingPolicy() {
  return useQuery({
    queryKey: ["household", "rating-policy"],
    staleTime: 60_000,
    queryFn: async () => (await api.GET("/api/v1/media/ratings/policy")).data as RatingPolicy,
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: ["household"] });
    void client.invalidateQueries({ queryKey: ["identity", "me"] });
    void client.invalidateQueries({ queryKey: NAVIGATION_KEY }); // issue 445: « My household » in the menu
  };
}

export function useCreateProfile() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: { display_name: string; kind: ProfileKind; color?: string; pin?: string }) =>
      (await api.POST("/api/v1/household/profiles", { body })).data as { id: string },
    onSuccess: refresh,
  });
}

export interface ProfileChanges {
  display_name?: string;
  color?: string;
  kind?: ProfileKind;
  restrictions?: RestrictionSettings;
  community_visible?: boolean;
}

export type HouseholdEconomy = "pot" | "dispatch";

/** Issue 445: the master makes its household (with its economy) — « My household » appears in the menu. */
export function useMakeHousehold() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (economy: HouseholdEconomy) => {
      const { error } = await api.POST("/api/v1/household/made", { body: { economy } });
      if (error) throw new Error("household.made");
    },
    onSuccess: refresh,
  });
}

/** Issue 445: a household without profiles undone — « My household » leaves the menu. */
export function useUnmakeHousehold() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async () => {
      const { error } = await api.DELETE("/api/v1/household/made");
      if (error) throw new Error("household.unmade");
    },
    onSuccess: refresh,
  });
}

/** Issue 443: the master chooses its household's economy (switching rebuilds or gives back the pot). */
export function useHouseholdEconomy() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (economy: HouseholdEconomy) => {
      const { error } = await api.PUT("/api/v1/household/economy", { body: { economy } });
      if (error) throw new Error("household.economy");
    },
    onSuccess: refresh,
  });
}

export function useUpdateProfile() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, ...body }: ProfileChanges & { id: string }) => {
      await api.PATCH("/api/v1/household/profiles/{profile_id}", {
        params: { path: { profile_id: id } },
        body,
      });
    },
    onSuccess: refresh,
  });
}

export function useDeleteProfile() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.DELETE("/api/v1/household/profiles/{profile_id}", { params: { path: { profile_id: id } } });
    },
    onSuccess: refresh,
  });
}

export function useSetPin() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, pin, current }: { id: string; pin: string | null; current?: string }) => {
      const { error } = await api.PUT("/api/v1/household/members/{member_id}/pin", {
        params: { path: { member_id: id } },
        body: { pin, ...(current ? { current } : {}) },
      });
      if (error) throw new Error("household.pin"); // a wrong current PIN, an invalid new one
    },
    onSuccess: refresh,
  });
}

export function useProfileActivity(id: string | null) {
  return useQuery({
    queryKey: ["household", "activity", id],
    enabled: Boolean(id),
    queryFn: async () =>
      (
        await api.GET("/api/v1/household/profiles/{profile_id}/activity", {
          params: { path: { profile_id: id as string } },
        })
      ).data as ProfileActivity,
  });
}

export function useAccessRequests(enabled = true) {
  return useQuery({
    queryKey: REQUESTS_KEY,
    enabled,
    queryFn: async () => (await api.GET("/api/v1/household/requests")).data as AccessRequest[],
  });
}

export function useAskAccess() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: { ref: string; title: string; rating?: string | null; note?: string }) =>
      (await api.POST("/api/v1/household/requests", { body: { kind: "media", ...body } })).data,
    onSuccess: refresh,
  });
}

export function useDecideAccess() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, approve, days }: { id: string; approve: boolean; days?: number }) => {
      await api.POST("/api/v1/household/requests/{request_id}/decision", {
        params: { path: { request_id: id } },
        body: { approve, ...(days ? { days } : {}) },
      });
    },
    onSuccess: refresh,
  });
}

export type ScreenTime = components["schemas"]["ScreenTimeOut"];

/** A profile's screen time today (``null``: none set). */
export function useScreenTime(profile: string | null, enabled = true, live = false) {
  return useQuery({
    queryKey: ["household", "screen", profile],
    enabled,
    refetchInterval: live ? 60_000 : false, // issue 436: the countdown follows what is watched
    retry: false,
    queryFn: async () =>
      (
        await api.GET("/api/v1/me/media/screen-time", {
          params: { query: profile ? { profile } : {} },
        })
      ).data as ScreenTime | null,
  });
}

/** Issue 432: minutes of screen time more today, for a profile (the master). */
export function useGiveMinutes() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, minutes }: { id: string; minutes: number }) => {
      const { error } = await api.POST("/api/v1/household/profiles/{profile_id}/minutes", {
        params: { path: { profile_id: id } },
        body: { minutes },
      });
      if (error) throw new Error("household.minutes");
    },
    onSuccess: refresh,
  });
}

/** Issue 432: no limits for a while (``minutes``), or the limits back now (``null``). */
export function useFreeProfile() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, minutes }: { id: string; minutes: number | null }) => {
      const { error } = await api.POST("/api/v1/household/profiles/{profile_id}/free", {
        params: { path: { profile_id: id } },
        body: { minutes },
      });
      if (error) throw new Error("household.free");
    },
    onSuccess: refresh,
  });
}

export const EXTRA_MINUTES = [15, 30, 60, 120] as const;

/** Minutes until the end of the day (local), within what the portal accepts. */
export function minutesLeftToday(now = new Date()): number {
  const midnight = new Date(now);
  midnight.setHours(24, 0, 0, 0);
  return Math.min(1440, Math.max(15, Math.ceil((midnight.getTime() - now.getTime()) / 60_000)));
}

export type FamilyActivity = components["schemas"]["FamilyActivityOut"];
export type FamilyMember = components["schemas"]["FamilyMemberOut"];

/** Issue 428: each member's watching, reading and playing lately (the household's dashboard). */
export function useFamilyActivity(days: number) {
  return useQuery({
    queryKey: ["household", "family", days],
    staleTime: 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/me/media/household", { params: { query: { days } } })).data as FamilyActivity,
  });
}
