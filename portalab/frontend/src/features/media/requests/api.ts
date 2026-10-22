import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";

/** My requests (027, after Telemetra's « Demandes » tab): statistics, list with posters, coming soon. */
export interface RequestCard {
  request_id: string;
  id: string | null;
  title: string;
  kind: "movie" | "series";
  state: string;
  requested_at: string;
  updated_at?: string;
  image_id: string | null;
  poster_ref?: string | null;
  route: string | null;
  /** 027: where it stands, in the words of the title's journey */
  stage?: string;
  progress?: number;
  at?: string;
  release_type?: string;
}

export interface SoonCard extends RequestCard {
  phase: "importing" | "downloading" | "queued" | "paused" | "warning" | "failed" | "release";
  progress?: number;
  count?: number;
  eta?: string | null;
  release_at?: string;
  release_type?: string;
  episode?: { season: number | null; episode: number | null; title: string };
}

export interface AudienceRates {
  available: number;
  seen_rate: number | null;
  viewers_per_request: number | null;
}

export interface RequestInsights {
  period: { key: string; start: string | null };
  summary: { total: number; pending: number; approved: number; available: number; declined: number };
  previous_total: number | null;
  by_kind: { movie: number; series: number };
  timeline: { unit: string; points: Array<{ date: string; count: number; previous: number }> };
  watched: { requested: number; watched: number; rate: number | null };
  ranking: { position: number | null; total: number; count: number; delta: number | null };
  top_watched: Array<{
    id: string;
    title: string;
    kind: string;
    plays: number;
    seconds: number;
    image_id: string | null;
    route: string | null;
  }>;
  genres: {
    requested: Array<{ name: string; value: number }>;
    watched: Array<{ name: string; value: number }>;
  };
  quota: { base_remaining?: number; extra_units?: number; [key: string]: unknown };
  acquisition?: Acquisition;
  /** issue 222: how many other members watched my requests (never who) */
  audience?: { requested: number; seen: number; viewers: number; plays: number };
  /** issue 222 (sold): my requests by audience, my rank by audience */
  audience_titles?: {
    items: Array<{
      id: string | null;
      title: string;
      kind: string;
      viewers: number;
      plays: number;
      image_id?: string | null;
      route?: string | null;
    }>;
    position: number | null;
    total: number;
  } | null;
  /** issue 222 (sold): the audience in depth */
  audience_depth?: {
    reactivity: {
      median_hours: number | null;
      buckets: Array<{ key: string; count: number }>;
      waiting: number;
      fastest: Array<{ title: string; hours: number }>;
      slowest: Array<{ title: string; hours: number }>;
    };
    genres: Record<"mine" | "server", Array<{ name: string; viewers: number; requests: number }>>;
    kinds: Record<"movie" | "series", AudienceRates & { requests: number; plays: number }>;
    versus: Record<"mine" | "server", AudienceRates>;
    late_share: number | null;
    over_time: { unit: string; points: Array<{ date: string; plays: number }> };
  } | null;
  /** issue 222 (sold): the requesters' podiums of the period */
  leaders?: Record<
    "requests" | "viewers" | "per_request",
    Array<{ rank: number; me: boolean; name: string | null; value: number; requests: number }>
  > | null;
  /** 061: the statistics still to unlock in the shop (their data left out) */
  locked?: string[];
}

export function useRequestInsights(period: string) {
  return useQuery({
    queryKey: ["media", "requests", "insights", period],
    queryFn: async () =>
      (await api.GET("/api/v1/me/media/requests/insights", { params: { query: { period } } }))
        .data as unknown as RequestInsights,
  });
}

export function useRequestList() {
  return useQuery({
    queryKey: ["media", "requests", "list"],
    queryFn: async () =>
      ((await api.GET("/api/v1/me/media/requests/list")).data as unknown as { items: RequestCard[] }).items,
  });
}

export function useSoon() {
  return useQuery({
    queryKey: ["media", "requests", "soon"],
    refetchInterval: 30_000, // downloads move: keep the progress fresh while the page is open
    queryFn: async () =>
      ((await api.GET("/api/v1/me/media/requests/soon")).data as unknown as { items: SoonCard[] }).items,
  });
}

export function posterOf(card: {
  image_id: string | null;
  poster_ref?: string | null | undefined;
}): string | null {
  if (card.image_id) return `/api/v1/media/images/${card.image_id}`;
  return card.poster_ref
    ? `/api/v1/media/metadata-images?ref=${encodeURIComponent(card.poster_ref)}&size=w342`
    : null;
}

/** Request states in four groups, like the funnel. */
export const GROUP_OF: Record<string, "pending" | "approved" | "available" | "declined"> = {
  pending: "pending",
  approved: "approved",
  processing: "approved",
  available: "available",
  declined: "declined",
  failed: "declined",
  cancelled: "declined",
};

export interface AcquisitionPoint {
  title: string;
  kind: string;
  hours: number;
  asked_after_days: number | null;
  moment: "before" | "month" | "year" | "catalog" | "unknown";
  id: string | null;
}

export interface Acquisition {
  buckets: Array<{ key: "hour" | "day" | "week" | "month" | "more"; count: number }>;
  pending: number;
  median_hours: number | null;
  moments: Array<{ moment: AcquisitionPoint["moment"]; count: number; median_hours: number | null }>;
  points: AcquisitionPoint[];
  fastest: AcquisitionPoint[];
  slowest: AcquisitionPoint[];
}
