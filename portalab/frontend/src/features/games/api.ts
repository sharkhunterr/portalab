import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../../api/client";
import { connectStream } from "../../api/stream";

/** Issue 265: the games page — its games, a game alone, the day's title, the week's challenge, the parties. */

export const ROUND_GAMES = [
  "poster",
  "casting",
  "synopsis",
  "higher_lower",
  "timeline",
  "blindtest",
  "memories",
  "whowatched",
] as const;
export type GameKey = (typeof ROUND_GAMES)[number] | "cinemot" | "memory" | "challenge";

export const GAME_ICONS: Record<string, string> = {
  poster: "image",
  casting: "users",
  synopsis: "book-open",
  higher_lower: "trending",
  timeline: "calendar-week",
  blindtest: "music",
  memories: "hourglass",
  whowatched: "eye",
  cinemot: "type",
  memory: "layers",
  challenge: "gamepad",
};

export interface Choice {
  id: string;
  label: string;
  image?: string | null;
}

export interface Question {
  game: string;
  prompt: Record<string, unknown> & {
    kind?: string;
    people?: { name: string; image: string | null }[];
    text?: string;
    criterion?: "rating" | "year" | "runtime";
    question?: "first" | "never";
    title?: string;
    year?: number | null;
    count?: number;
  };
  choices: Choice[];
  ordered: boolean;
  image: boolean;
  audio: boolean;
}

export interface Reveal {
  title?: string;
  year?: number | null;
  poster?: string | null;
  id?: string;
  who?: string;
  values?: Record<string, string | number | null>;
}

export interface Result {
  correct: boolean;
  points: number;
  given?: unknown;
  answer?: string | string[];
  reveal?: Reveal;
}

export interface MemoryFace {
  key: string;
  card?: Record<string, unknown>;
  poster?: string;
  title?: string;
}

export interface SoloView {
  id: string;
  game: string;
  status: "playing" | "done";
  score: number;
  correct: number;
  rounds: number;
  results: { correct: boolean; points: number }[];
  now: string;
  round?: number;
  phase?: "question" | "reveal";
  seconds?: number;
  started?: string;
  deadline?: string;
  question?: Question;
  result?: Result;
  last?: { reveal?: Reveal; correct?: boolean } | null;
  board?: { state: "hidden" | "open" | "matched"; face: MemoryFace | null }[];
  moves?: number;
  pairs?: number;
}

export interface HubGame {
  key: GameKey;
  kind: string;
  solo: boolean;
  party: boolean;
  rounds?: number;
  seconds?: number;
  best_week?: number | null;
}

export interface PartyRef {
  code: string;
  game: string;
  status: string;
  host: boolean;
}

export interface Hub {
  enabled: boolean;
  games: HubGame[];
  party: boolean;
  cinemot: { status: string; won: boolean } | null;
  parties: PartyRef[];
}

export interface CinemotView {
  id: string;
  day: string;
  pattern: number[];
  hints: { kind?: string; year?: number | null; genres?: string[] };
  guesses: { letters: string; marks: string }[];
  tries: number;
  status: "playing" | "done";
  won: boolean;
  score: number;
  answer?: { title: string; year: number | null; poster: string | null; id: string; word: string };
}

export interface ChallengeItem {
  kind: "game" | "movie" | "book" | "audiobook";
  week: string;
  ends_at: string;
  title: { id: string; title: string; platform: string | null; image_id: string | null };
  target: number;
  unit: "minutes" | "percent";
  mine: number;
  done: boolean;
  finishers: number;
}

export interface ChallengeView {
  items: ChallengeItem[];
}

export interface PartyPlayer {
  id: string;
  name: string | null;
  score: number;
  rank: number | null;
  answered: boolean;
  points: number | null;
  me: boolean;
}

export interface PartyView {
  code: string;
  game: string;
  status: "lobby" | "playing" | "done" | "closed";
  version: number;
  host: string | null;
  is_host: boolean;
  playing: boolean;
  settings: { rounds: number; seconds: number; choices: number; host_plays: boolean };
  now: string;
  players: PartyPlayer[];
  round?: number;
  rounds?: number;
  phase?: "question" | "reveal";
  started?: string;
  deadline?: string;
  question?: Question | null;
  given?: unknown;
  reveal?: { answer: string | string[]; reveal: Reveal; mine: Result | null; next_at: string };
  last?: { reveal?: Reveal } | null;
}

export interface BoardView {
  game: string;
  period: string;
  entries: { rank: number; name: string | null; value: number; me: boolean }[];
  me: { rank: number; value: number } | null;
}

const KEY = ["games"] as const;

export function metadataImage(ref: string | null | undefined, size = "w342"): string | null {
  return ref ? `/api/v1/media/metadata-images?ref=${encodeURIComponent(ref)}&size=${size}` : null;
}

export function useGamesHub() {
  return useQuery({
    queryKey: [...KEY, "hub"],
    queryFn: async () => (await api.GET("/api/v1/games")).data as unknown as Hub,
  });
}

export function useBoard(game: string, period: string) {
  return useQuery({
    queryKey: [...KEY, "board", game, period],
    queryFn: async () =>
      (await api.GET("/api/v1/games/leaderboard", { params: { query: { game, period } as never } }))
        .data as unknown as BoardView,
  });
}

export function useChallenge(enabled = true) {
  return useQuery({
    queryKey: [...KEY, "challenge"],
    enabled,
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/games/challenge")).data as unknown as ChallengeView,
  });
}

export function useCinemot() {
  return useQuery({
    queryKey: [...KEY, "cinemot"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/games/cinemot")).data as unknown as CinemotView,
  });
}

export function useGuess() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (guess: string) =>
      (await api.POST("/api/v1/games/cinemot/guesses", { body: { guess } })).data as unknown as CinemotView,
    onSuccess: (view) => {
      client.setQueryData([...KEY, "cinemot"], view);
      if (view.status === "done") void client.invalidateQueries({ queryKey: [...KEY, "hub"] });
    },
  });
}

export function useSession(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, "session", id],
    enabled: Boolean(id),
    queryFn: async () =>
      (await api.GET("/api/v1/games/sessions/{session_id}", { params: { path: { session_id: id ?? "" } } }))
        .data as unknown as SoloView,
  });
}

export function useStart() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (game: string) =>
      game === "memory"
        ? ((await api.POST("/api/v1/games/memory/sessions")).data as unknown as SoloView)
        : ((await api.POST("/api/v1/games/{game}/sessions", { params: { path: { game } } }))
            .data as unknown as SoloView),
    onSuccess: (view) => client.setQueryData([...KEY, "session", view.id], view),
  });
}

/** An action on a game alone (an answer, the next question, a card turned over): the new state of it. */
export function useSessionAction(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (
      action:
        | { kind: "answer"; choice?: string; order?: string[] }
        | { kind: "next" }
        | { kind: "flip"; position: number },
    ) => {
      const path = { session_id: id };
      if (action.kind === "answer") {
        const body = action.order ? { order: action.order } : { choice: action.choice ?? null };
        return (await api.POST("/api/v1/games/sessions/{session_id}/answer", { params: { path }, body }))
          .data as unknown as SoloView;
      }
      if (action.kind === "flip") {
        return (
          await api.POST("/api/v1/games/sessions/{session_id}/flip", {
            params: { path },
            body: { position: action.position },
          })
        ).data as unknown as SoloView;
      }
      return (await api.POST("/api/v1/games/sessions/{session_id}/next", { params: { path } }))
        .data as unknown as SoloView;
    },
    onSuccess: (view) => {
      client.setQueryData([...KEY, "session", id], view);
      if (view.status === "done") void client.invalidateQueries({ queryKey: [...KEY, "hub"] });
    },
  });
}

/** A party, told live of every change (``games.party``) and looked at now and then while it is played. */
export function useParty(code: string | undefined) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: [...KEY, "party", code],
    enabled: Boolean(code),
    retry: false,
    refetchInterval: (q) => {
      const status = (q.state.data as PartyView | undefined)?.status;
      return status === "playing" ? 1500 : status === "lobby" ? 4000 : false;
    },
    queryFn: async () =>
      (await api.GET("/api/v1/games/parties/{code}", { params: { path: { code: code ?? "" } } }))
        .data as unknown as PartyView,
  });
  useEffect(() => {
    if (!code) return undefined;
    const stream = connectStream({
      topics: ["games.party"],
      onEvent: (event) => {
        const data = event.data as { code?: string } | null;
        if (data?.code === code) void client.invalidateQueries({ queryKey: [...KEY, "party", code] });
      },
    });
    return () => stream.close();
  }, [code, client]);
  return query;
}

export function usePartyAction(code: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (
      action:
        | { kind: "join" | "start" | "next" | "leave" }
        | { kind: "answer"; choice?: string; order?: string[] },
    ) => {
      const path = { code };
      if (action.kind === "answer") {
        const body = action.order ? { order: action.order } : { choice: action.choice ?? null };
        return (await api.POST("/api/v1/games/parties/{code}/answer", { params: { path }, body }))
          .data as unknown as PartyView;
      }
      if (action.kind === "leave") {
        await api.POST("/api/v1/games/parties/{code}/leave", { params: { path } });
        return null;
      }
      const route = {
        join: "/api/v1/games/parties/{code}/join",
        start: "/api/v1/games/parties/{code}/start",
        next: "/api/v1/games/parties/{code}/next",
      } as const;
      return (await api.POST(route[action.kind], { params: { path } })).data as unknown as PartyView;
    },
    onSuccess: (view) => {
      if (view) client.setQueryData([...KEY, "party", code], view);
      void client.invalidateQueries({ queryKey: [...KEY, "hub"] });
    },
  });
}

export function useOpenParty() {
  return useMutation({
    mutationFn: async (body: {
      game: string;
      rounds?: number | null;
      seconds?: number | null;
      host_plays: boolean;
    }) => (await api.POST("/api/v1/games/parties", { body })).data as unknown as PartyView,
  });
}

/** The server's clock against mine: a question's deadline is the server's. */
export function skewOf(serverNow: string | undefined): number {
  return serverNow ? new Date(serverNow).getTime() - Date.now() : 0;
}
export const BLUR_STEPS = 6; // as many as the server blurs a poster (the last one sharp)
