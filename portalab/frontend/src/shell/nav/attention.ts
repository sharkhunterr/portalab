import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { NavEntry, NavSection } from "./NavigationProvider";

/**
 * #98 — what waits for me, per navigation entry (``GET /me/attention``), checked every minute and when
 * the window comes back: an entry shows its own count, a hub and a section the sum of theirs.
 */
export function useAttention() {
  const query = useQuery({
    queryKey: ["shell", "attention"],
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    staleTime: 20_000,
    retry: false,
    queryFn: async () => {
      const { data } = await api.GET("/api/v1/me/attention");
      return (data?.items ?? {}) as Record<string, number>;
    },
  });
  const counts = query.data ?? {};
  const of = (entry: Pick<NavEntry, "key">) => counts[entry.key] ?? 0;
  const ofEntries = (entries: readonly Pick<NavEntry, "key">[]) => entries.reduce((sum, e) => sum + of(e), 0);
  const ofSection = (section: NavSection) =>
    ofEntries(section.entries) + section.topics.reduce((sum, topic) => sum + ofEntries(topic.entries), 0);
  return { counts, of, ofEntries, ofSection };
}
