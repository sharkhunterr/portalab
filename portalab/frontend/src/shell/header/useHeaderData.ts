import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "../../api/client";
import { connectStream, type LiveEvent } from "../../api/stream";
import { useCelebrate } from "../../design-system/feedback/Celebration";
import { useMe } from "../../features/auth/useAuth";
import type { Progression } from "../../features/gamification/api";
import { showLevelUp } from "../../features/gamification/levelup/LevelUpMoment";
import { useUnreadCount } from "../../features/notifications/api";
import { useT } from "../../i18n/hooks/useT";

/**
 * Header data (spec 027 R5/R6, FR-004/005): identity, progression and unread count come from their own
 * endpoints, each loading and failing on its own — an unavailable gamification module only hides the
 * level/Coins chips. ``progression.changed`` live events patch the cached progression (no polling) and
 * trigger the celebration: a short one for gains, a bigger one when a level is crossed.
 */
export const PROGRESSION_KEY = ["gamification", "progression"] as const;

export interface ProgressionChange {
  xp: number;
  level: number;
  level_floor: number;
  next_level_at: number | null;
  coins: number;
  delta_xp: number;
  delta_coins: number;
  level_up: boolean;
}

function isChange(data: unknown): data is ProgressionChange {
  return typeof data === "object" && data !== null && "xp" in data && "coins" in data && "level" in data;
}

export function useHeaderData() {
  const me = useMe();
  const signedIn = Boolean(me.data);
  const progression = useQuery({
    queryKey: PROGRESSION_KEY,
    enabled: signedIn,
    retry: false,
    staleTime: 60_000,
    queryFn: async () => (await api.GET("/api/v1/me/progression")).data as Progression,
  });
  const unread = useUnreadCount(signedIn);
  useLiveProgression(signedIn);
  const userId = me.data?.id ?? null;
  return {
    me: me.data ?? null,
    avatarUrl: userId && me.data?.has_avatar ? `/api/v1/users/${userId}/avatar` : null,
    progression: progression.isError ? null : (progression.data ?? null),
    progressionState: progression.isError ? "unavailable" : progression.isPending ? "loading" : "ready",
    unread: unread.isError ? null : (unread.data ?? 0),
  } as const;
}

function useLiveProgression(enabled: boolean) {
  const client = useQueryClient();
  const celebrate = useCelebrate();
  const t = useT();
  const seen = useRef(new Set<string>());
  // latest celebrate/t without re-subscribing to the stream on every render
  const latest = useRef({ celebrate, t });
  latest.current = { celebrate, t };
  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") return;
    const handle = connectStream({
      topics: ["progression.changed"],
      onEvent: (event: LiveEvent) => {
        if (!isChange(event.data) || seen.current.has(event.id)) return;
        seen.current.add(event.id);
        const before = client.getQueryData<Progression>(PROGRESSION_KEY)?.level;
        applyChange(client, event.data);
        const change = event.data;
        const { celebrate, t } = latest.current;
        if (change.level_up) {
          // 027: the level-up moment — the new level, what it brought and what it unlocked
          showLevelUp({ level: change.level, from: before, xp: change.delta_xp || undefined });
          celebrate({ kind: "level", text: t("shell:levelReached", { level: change.level }) });
        } else if (change.delta_xp > 0) {
          celebrate({ kind: "reward", text: t("shell:xpGained", { amount: change.delta_xp }) });
        } else if (change.delta_coins > 0) {
          celebrate({ kind: "reward", text: t("shell:coinsGained", { amount: change.delta_coins }) });
        }
      },
    });
    return () => handle.close();
  }, [enabled, client]);
}

export function applyChange(client: ReturnType<typeof useQueryClient>, change: ProgressionChange): void {
  client.setQueryData<Progression | undefined>(PROGRESSION_KEY, (old) =>
    old
      ? {
          ...old,
          xp: change.xp,
          level: change.level,
          level_floor: change.level_floor,
          next_level_at: change.next_level_at,
          coins: change.coins,
        }
      : old,
  );
}
