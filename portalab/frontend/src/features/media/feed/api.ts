import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";

/** « Mon fil » API hooks (#299): what I follow (private), and what it brings. */
export type Follow = components["schemas"]["FollowOut"];
export type FollowKind = Follow["kind"];
export type Feed = components["schemas"]["FeedOut"];
export type FeedItem = components["schemas"]["FeedItemOut"];
export type FeedUpcoming = components["schemas"]["FeedUpcomingOut"];

const KEY = ["media", "feed"] as const;
const ATTENTION = ["shell", "attention"] as const;

export function useFollows() {
  return useQuery({
    queryKey: [...KEY, "follows"],
    queryFn: async () => (await api.GET("/api/v1/me/media/follows")).data?.items ?? [],
  });
}

/** Follow (``on``) or stop following a person, a title or a genre; the feed and its badge follow. */
export function useFollowToggle() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, ref, on }: { kind: FollowKind; ref: string; on: boolean }) => {
      if (on) {
        const { error } = await api.PUT("/api/v1/me/media/follows", { body: { kind, ref } });
        if (error) throw error;
      } else {
        await api.DELETE("/api/v1/me/media/follows", { params: { query: { kind, ref } } });
      }
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ATTENTION });
    },
  });
}

export function useFeed() {
  return useQuery({
    queryKey: [...KEY, "items"],
    queryFn: async () => (await api.GET("/api/v1/me/media/feed")).data as Feed,
  });
}

/** I read my feed: its badge goes. */
export function useMarkSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/me/media/feed/seen");
    },
    onSettled: () => void client.invalidateQueries({ queryKey: ATTENTION }),
  });
}

function folded(name: string): string {
  return name.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase().trim();
}

/** #299: whether I follow a person (by name, however it is written) or a title (by its id). */
export function useFollowed() {
  const follows = useFollows().data ?? [];
  const people = new Set(follows.filter((f) => f.kind === "person").map((f) => folded(f.label)));
  const titles = new Set(follows.filter((f) => f.kind === "title").map((f) => f.ref));
  return {
    person: (name: string) => people.has(folded(name)),
    title: (id: string) => titles.has(id),
  };
}
