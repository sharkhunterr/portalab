import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";

/** Media statistics (027): what was watched, listened to and read — mine or the server's. */
export type Scope = "me" | "all";
export type Category =
  | "all"
  | "movies"
  | "series"
  | "live"
  | "music"
  | "books"
  | "audiobooks"
  | "radio"
  | "games";
export const CATEGORIES: Category[] = [
  "all",
  "movies",
  "series",
  "live",
  "music",
  "books",
  "audiobooks",
  "radio",
  "games",
];
export const PERIODS = ["7d", "30d", "90d", "ytd", "365d", "all"] as const;

export interface Work {
  id: string | null;
  title: string;
  kind: string;
  year: number | null;
  plays: number;
  seconds: number;
  members: number | null;
  last_at: string | null;
  image_id: string | null;
  /** 027: the metadata provider's poster when the library has none (live TV, a title seen elsewhere). */
  poster_ref?: string | null;
}

export interface Ranked {
  name: string;
  plays: number;
  seconds: number;
  works?: number;
  /** 027: a person's portrait (the metadata provider's image ref). */
  image?: string | null;
}

export interface Insights {
  period: { key: string; start: string | null; end: string };
  scope: Scope;
  category: Category;
  manager: boolean;
  totals: {
    plays: number;
    completed: number;
    seconds: number;
    active_days: number;
    works: number;
    members: number | null;
  };
  previous: { plays: number; seconds: number } | null;
  by_kind: Array<{ kind: string; plays: number; seconds: number }>;
  timeline: {
    unit: "day" | "week" | "month";
    points: Array<{
      date: string;
      seconds: Record<string, number>;
      plays: number;
      /** 027: plays per kind (stacked like the time) */
      plays_by_kind?: Record<string, number>;
    }>;
  };
  heatmap: Array<{ weekday: number; hour: number; plays: number; seconds: number }>;
  top_works: Work[];
  genres: Ranked[];
  people: Ranked[];
  decades: Array<{ decade: number; plays: number; seconds: number }>;
  records: {
    longest: { title: string; parent_title: string | null; seconds: number; at: string } | null;
    busiest_day: { date: string; seconds: number; plays: number } | null;
    best_streak: number;
    completed: number;
    first_at: string | null;
  };
  box_office: {
    films: number;
    budget: number;
    revenue: number;
    with_budget: number;
    top: Array<{ id: string; title: string; revenue: number; image_id: string | null }>;
  } | null;
  platforms: Ranked[] | null;
  /** 027: sections sold in the shop that this member has not unlocked (their data is left out). */
  locked?: string[];
  recent: Array<{
    title: string;
    parent_title: string | null;
    kind: string;
    work_id: string | null;
    at: string;
    seconds: number;
    progress: number | null;
    member?: string | null;
    platform: string | null;
    image_id?: string | null;
    poster_ref?: string | null;
  }> | null;
  members: Array<{
    user_id: string | null;
    name?: string | null;
    plays: number;
    seconds: number;
    completed: number;
    active_days: number;
    last_day: string;
  }> | null;
  requests: {
    total: number;
    states: Record<string, number>;
    kinds: Record<string, number>;
    available_rate: number | null;
  } | null;
  unattributed: number | null;
}

export interface Source {
  service_id: string;
  name: string;
  source: string;
  mode: "backfill" | "incremental";
  items: number;
  watermark: string | null;
  backfilled_at: string | null;
  last_run_at: string | null;
  last_error: string | null;
  behind_since?: string | null; // #24: a richest source no longer receiving plays, since its latest one
  progress: TaskProgress;
}

export interface TaskProgress {
  running: boolean;
  since: string | null;
  done: number | null;
  total: number | null;
}

export interface Sources {
  sources: Source[];
  metadata: {
    provider: boolean;
    found: number;
    missing: number;
    error: number;
    eligible: number;
    progress: TaskProgress;
  };
  unattributed: number;
}

/** 027: the statistics in depth — one tab each, compared with the previous period of the same length. */
export type Section = "casting" | "production" | "playback" | "profile";

interface SectionBase {
  section: Section;
  unit: "day" | "week" | "month";
  buckets: string[];
  has_previous: boolean;
}

export interface Person {
  name: string;
  image: string | null;
  works: number;
  seconds: number;
  previous: number;
  titles: string[];
}

export interface Casting extends SectionBase {
  directors: Person[];
  actors: Person[];
  with_metadata: number;
}

export interface Film {
  id: string;
  title: string;
  poster_ref: string | null;
  image_id?: string | null;
  budget: number | null;
  revenue: number | null;
  roi: number | null;
  year: number | null;
}

export interface Production extends SectionBase {
  films: number;
  years: Array<{ year: number; count: number; previous: number }>;
  year_average: number | null;
  year_average_previous: number | null;
  countries: Array<{ code: string; count: number }>;
  most_expensive?: Film | null;
  cheapest?: Film | null;
  most_profitable?: Film | null;
  budget_average?: number | null;
  budgets?: Array<{ range: string; count: number; previous: number }>;
  successes?: Film[];
  flops?: Film[];
}

export interface Breakdown {
  totals: Array<{ key: string; count: number; previous: number }>;
  series: Array<{ current: Record<string, number>; previous: Record<string, number> }>;
}

export interface Playback extends SectionBase {
  total: number;
  total_previous: number;
  streams: Breakdown;
  qualities: Breakdown;
  platforms: Array<{ name: string; count: number }>;
  devices: Array<{ name: string; count: number }> | null;
}

export interface Profile extends SectionBase {
  genres: Array<{ name: string; count: number; previous: number }>;
  summary: { new: string[]; rising: string[]; always: string[]; gone: string[] };
  genre_series: string[];
  genre_buckets: Array<Record<string, number>>;
  activity: Array<{ plays: number; completed: number; previous_plays: number; previous_completed: number }>;
  hours: number[];
  weekdays: number[];
}

export interface SectionData {
  casting: Casting;
  production: Production;
  playback: Playback;
  profile: Profile;
}

export function useInsightSection<S extends Section>(
  section: S,
  scope: Scope,
  category: Category,
  period: string,
) {
  const { time_zone } = useLocaleContext();
  return useQuery({
    queryKey: ["media", "insights", section, scope, category, period, time_zone],
    staleTime: 60_000,
    queryFn: async () =>
      (
        await api.GET("/api/v1/media/insights/{section}", {
          params: {
            path: { section },
            query: { scope, category, period, tz: time_zone || "UTC" },
          },
        })
      ).data as unknown as SectionData[S],
  });
}

/** When an update was last asked for: the panel refreshes quickly until it shows up as running. */
let requestedAt = 0;

/** 061: the statistics on sale this member has not unlocked (``media.insights.*``, ``media.requests.*``). */
export function useLockedStatistics() {
  const query = useQuery({
    queryKey: ["media", "insights", "locked"],
    staleTime: 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/me/media/insights/locked")).data as { locked: string[] } | undefined)
        ?.locked ?? [],
  });
  const locked = new Set(query.data ?? []);
  return {
    tab: (section: string) => locked.has(`media.insights.tab.${section}`),
    history: locked.has("media.insights.history"),
    server: locked.has("media.insights.server"),
  };
}

/** 061: a long period (the year to date, one year, all time) — sold with the « full history ». */
export const LONG_PERIOD = /^(ytd|all|\d{4})$/;

export function useInsights(scope: Scope, category: Category, period: string, enabled = true) {
  const { time_zone } = useLocaleContext();
  return useQuery({
    enabled,
    queryKey: ["media", "insights", scope, category, period, time_zone],
    queryFn: async () =>
      (
        await api.GET("/api/v1/media/insights", {
          params: { query: { scope, category, period, tz: time_zone || "UTC" } },
        })
      ).data as unknown as Insights,
  });
}

/** Issue 283: the tabs a configured service feeds (and « requests » when a request service is connected). */
export function useInsightCategories() {
  return useQuery({
    queryKey: ["media", "insights", "categories"],
    staleTime: 5 * 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/media/insights/categories")).data?.categories ?? ["all"]) as string[],
  });
}

export function useSources(enabled: boolean) {
  return useQuery({
    queryKey: ["media", "insights", "sources"],
    enabled,
    retry: false,
    refetchInterval: (query) => {
      const data = query.state.data as Sources | undefined;
      const running =
        data?.metadata.progress.running || (data?.sources ?? []).some((source) => source.progress.running);
      return running || Date.now() - requestedAt < 30_000 ? 2000 : false;
    },
    queryFn: async () => (await api.GET("/api/v1/admin/media/insights/sources")).data as unknown as Sources,
  });
}

export function useResync() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (serviceId: string) => {
      requestedAt = Date.now();
      return api.POST("/api/v1/admin/media/insights/sources/{service_id}/resync", {
        params: { path: { service_id: serviceId } },
      });
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: ["media", "insights", "sources"] }),
  });
}

/** Localized durations and amounts (Intl units: « 12 h », « 45 min », « 1,2 Md $ »). */
export function useMeasures() {
  const { locale } = useLocaleContext();
  const unit = (value: number, name: "hour" | "minute" | "day") =>
    new Intl.NumberFormat(locale, {
      style: "unit",
      unit: name,
      unitDisplay: "short",
      maximumFractionDigits: 0,
    }).format(value);
  return {
    duration: (seconds: number) => {
      if (seconds < 3600) return unit(Math.round(seconds / 60), "minute");
      const hours = seconds / 3600;
      if (hours < 10) {
        const whole = Math.floor(hours);
        const minutes = Math.round((hours - whole) * 60);
        return minutes ? `${unit(whole, "hour")} ${unit(minutes, "minute")}` : unit(whole, "hour");
      }
      return unit(Math.round(hours), "hour");
    },
    hours: (seconds: number) => unit(Math.round(seconds / 3600), "hour"),
    /** #58: a size in the locale's own units (« 977 Mo », « 977 MB »). */
    bytes: (value: number) => {
      const units = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"] as const;
      let amount = value;
      let index = 0;
      while (amount >= 1024 && index < units.length - 1) {
        amount /= 1024;
        index += 1;
      }
      return new Intl.NumberFormat(locale, {
        style: "unit",
        unit: units[index],
        unitDisplay: "short",
        maximumFractionDigits: amount >= 10 || index === 0 ? 0 : 1,
      }).format(amount);
    },
    money: (amount: number) =>
      new Intl.NumberFormat(locale, {
        style: "currency",
        currency: "USD",
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(amount),
    weekday: (isoDay: number) =>
      new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(
        new Date(Date.UTC(2024, 0, isoDay)), // 2024-01-01 is a Monday (ISO day 1)
      ),
    compact: (value: number) => new Intl.NumberFormat(locale, { notation: "compact" }).format(value),
  };
}

export function useRunNow() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (what: "history" | "metadata") => {
      requestedAt = Date.now();
      return api.POST("/api/v1/admin/media/insights/run", { body: { what } });
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: ["media", "insights"] }),
  });
}
