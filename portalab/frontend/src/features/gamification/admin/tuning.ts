import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import type { Translate } from "../../../i18n/hooks/useT";
import type { LedgerValue, Value } from "../api";

/**
 * Gamification tuning (027): the data behind the administration tabs — rewardable actions, play streaks,
 * level rewards, progress over time, achievements and quests as typed forms (never raw JSON first).
 */
export type EventTypeInfo = components["schemas"]["EventTypeOut"];
export type StreakConfig = Required<components["schemas"]["StreakConfig"]>;
export type LevelReward = components["schemas"]["LevelReward"];
export type LevelRewards = components["schemas"]["LevelRewardsOut"];
export type Progress = components["schemas"]["ProgressOut"];
export type MembersProgress = components["schemas"]["MembersProgressOut"];
export type MemberDetail = components["schemas"]["MemberDetailOut"];
export type Operation = components["schemas"]["OperationOut"];
type Operations = components["schemas"]["OperationsOut"];

export const VALUES: Value[] = ["xp", "coins", "contribution"];
// issue 234: the journal and the charts follow the boosters the rules give too
export const LEDGER_VALUES: LedgerValue[] = [...VALUES, "booster"];
const KEY = ["gamification", "admin"] as const;

export interface Condition {
  field: string;
  op: "eq" | "ne" | "in" | "gt" | "gte" | "lt" | "lte";
  value: string | number | boolean | Array<string | number>;
}

export interface RuleGrant {
  value: Value;
  amount?: number | null;
  per_unit?: { field: string; factor: number; max?: number | null } | null;
}

export interface RuleDefinition {
  event_type: string;
  label?: string;
  predicate?: Condition[];
  grants: RuleGrant[];
  /** Issue 234: boosters of the event's content (a film, a season), once per member and content. */
  boosters?: number;
  multiplier?: number;
  limits?: {
    cooldown_seconds?: number;
    caps?: Array<{ period: "hour" | "day" | "week"; max_amount: number; value?: Value | null }>;
    diminishing?: unknown;
  };
}

export interface EventCount {
  kind: "event_count";
  event_type: string;
  filter?: Condition[];
  count: number;
}

export type Criterion =
  | EventCount
  | { kind: "level_at_least"; level: number }
  | { kind: "value_at_least"; value: Value; amount: number }
  | { kind: "statistic_at_least"; statistic: string; amount: number };

export interface Reward {
  value: Value;
  amount: number;
}

export interface AchievementDefinition {
  label: string;
  description?: string | undefined;
  icon?: string | null | undefined;
  hidden?: boolean | undefined;
  category?: string | undefined;
  criteria: Criterion[];
  rewards?: Reward[] | undefined;
  /** shop products it gives (a badge, a title, a frame… or a sealed booster) */
  unlocks?: Unlock[] | undefined;
}

export interface Unlock {
  product: string;
  kind: string;
  label: string;
}

/** The kinds of shop products an achievement may give. */
export const UNLOCK_KINDS = [
  "badge", "title", "avatar_frame", "profile_banner", "profile_background", "name_style", "level_badge",
  "level_up", "notification_style", "notification_animation", "effect", "ambient", "palette", "theme", "booster",
] as const; // biome-ignore format: a list

export interface QuestDefinition {
  kind: "quest" | "daily" | "challenge" | "discovery";
  label: string;
  description?: string | undefined;
  icon?: string | null | undefined;
  period?: "none" | "day" | "week" | "month" | undefined;
  window?: { starts_at: string; ends_at: string } | null | undefined;
  steps: EventCount[];
  /** Issue 121: done when every step is (``all``, the default) or any one of them. */
  complete_on?: "all" | "any" | undefined;
  rewards?: Reward[] | undefined;
  /** Issue 307: its texts in other interface languages (the shipped ones in French). */
  translations?: Record<string, { label: string; description?: string }> | undefined;
}

export interface Versioned<T> {
  key: string;
  version: number;
  definition: T;
  source: string;
}

/** A readable name for an action (event type): the translated one when known, else the type itself. */
export function actionLabel(t: Translate, name: string): string {
  const id = `gamification:action.${name.replaceAll(".", "_")}`;
  const label = t(id);
  return label === id.split(":")[1] ? name : label;
}

/** Durations are counted per minute in forms; events carry seconds. */
export const PER_MINUTE_FIELDS = new Set(["duration_s", "position_s", "watched_s", "played_s", "length_s"]);

/** The actions a rule may reward; issue 309: with ``goals``, also what an achievement or a quest may count of
 * the progression itself (a quest done, an achievement unlocked, a level reached). */
export function useEventTypes(goals = false) {
  return useQuery({
    queryKey: [...KEY, "event-types", goals],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/gamification/event-types", { params: { query: { goals } } })).data ??
        []) as EventTypeInfo[],
    staleTime: 5 * 60_000,
  });
}

export function useStreak() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: [...KEY, "streak"],
    queryFn: async () => (await api.GET("/api/v1/admin/gamification/streak")).data as StreakConfig,
    // the server always fills every field (defaults included)
  });
  const save = useMutation({
    mutationFn: async (body: StreakConfig) =>
      (await api.PUT("/api/v1/admin/gamification/streak", { body })).data as StreakConfig,
    onSuccess: (data) => client.setQueryData([...KEY, "streak"], data),
  });
  return { query, save };
}

export function useLevelRewards() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: [...KEY, "level-rewards"],
    queryFn: async () => (await api.GET("/api/v1/admin/gamification/level-rewards")).data as LevelRewards,
  });
  const save = useMutation({
    mutationFn: async (rewards: LevelReward[]) =>
      (await api.PUT("/api/v1/admin/gamification/level-rewards", { body: { rewards } })).data as LevelRewards,
    onSuccess: (data) => client.setQueryData([...KEY, "level-rewards"], data),
  });
  return { query, save };
}

export function useProgress(value: LedgerValue, days: number) {
  return useQuery({
    queryKey: [...KEY, "progress", value, days],
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/gamification/progress", {
          params: { query: { value, days, top: 5 } },
        })
      ).data as Progress,
  });
}

/** Issue 104: every member's progression over the period — gains by kind, day by day, running balance. */
export function useMembersProgress(value: LedgerValue, days: number) {
  return useQuery({
    queryKey: [...KEY, "members", value, days],
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/gamification/members", {
          params: { query: { value, days } },
        })
      ).data as MembersProgress,
  });
}

/** Issue 106: each member's XP, levels, Coins and Contribution over the period, in all and day by day. */
export function useMembersDetails(days: number) {
  return useQuery({
    queryKey: [...KEY, "members-details", days],
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/gamification/members/details", {
          params: { query: { days } },
        })
      ).data?.members ?? ([] as MemberDetail[]),
  });
}

/** Issue 107: one page of every member's operations (or one member's), the latest first; issue 114: or mine. */
export function useOperations(
  days: number,
  member: string,
  value: LedgerValue | "",
  cursor: string | null,
  limit: number,
  mine = false,
  play = "",
) {
  return useQuery({
    queryKey: [...KEY, "operations", mine, days, member, value, cursor, limit, play],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const query = {
        days,
        limit,
        ...(value ? { value } : {}),
        ...(cursor ? { cursor } : {}),
        ...(play ? { play } : {}),
      };
      const result = mine
        ? await api.GET("/api/v1/me/progression/operations", { params: { query } })
        : await api.GET("/api/v1/admin/gamification/operations", {
            params: { query: { ...query, ...(member ? { member } : {}) } },
          });
      return result.data ?? ({ items: [], next_cursor: null, total: 0 } as Operations);
    },
  });
}

function useVersioned<T>(path: "achievements" | "quests") {
  const client = useQueryClient();
  const key = [...KEY, path];
  const query = useQuery({
    queryKey: key,
    queryFn: async () =>
      ((path === "achievements"
        ? (await api.GET("/api/v1/admin/gamification/achievements")).data
        : (await api.GET("/api/v1/admin/gamification/quests")).data) ?? []) as unknown as Versioned<T>[],
  });
  const save = useMutation({
    mutationFn: async ({ key: item, definition }: { key: string; definition: T }) => {
      const options = {
        params: { path: { key: item } },
        body: { definition: definition as unknown as Record<string, unknown> },
      };
      return path === "achievements"
        ? api.PUT("/api/v1/admin/gamification/achievements/{key}", options)
        : api.PUT("/api/v1/admin/gamification/quests/{key}", options);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  const retire = useMutation({
    mutationFn: async (item: string) => {
      const options = { params: { path: { key: item } } };
      return path === "achievements"
        ? api.DELETE("/api/v1/admin/gamification/achievements/{key}", options)
        : api.DELETE("/api/v1/admin/gamification/quests/{key}", options);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  return { query, save, retire };
}

export const useAchievementAdmin = () => useVersioned<AchievementDefinition>("achievements");
export const useQuestAdmin = () => useVersioned<QuestDefinition>("quests");

export interface ShopProduct {
  key: string;
  name: string;
  type: string;
  state: string;
  min_level?: number | null;
  price_coins?: number | null;
}

export function useShopProducts() {
  return useQuery({
    queryKey: [...KEY, "products"],
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/marketplace/products")).data ?? []) as unknown as ShopProduct[],
    staleTime: 60_000,
  });
}

/** A key from a label: lower case, dots and underscores only (the server's key pattern). */
export function keyOf(label: string): string {
  return label
    .normalize("NFKD")
    .replace(/[^\w\s.]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_")
    .replace(/^[^a-z]+/, "")
    .slice(0, 60);
}
