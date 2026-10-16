import { z } from "zod";
import { api } from "../../../api/client";
import type { Contract } from "./types";

const schema = z.object({
  streak_days: z.number().int(),
  streak_multiplier: z.number(),
  achievements: z.number().int(),
});

/** ``me.statistics``: the member's own figures — their streak of days, its bonus, their achievements. */
export const statistics: Contract<z.infer<typeof schema>> = {
  key: "me.statistics",
  permission: "users.self.manage",
  refreshS: 300,
  sources: [
    {
      queryKey: ["gamification", "my-streak"],
      queryFn: async () => (await api.GET("/api/v1/me/streak")).data,
    },
    {
      queryKey: ["gamification", "progression"],
      queryFn: async () => (await api.GET("/api/v1/me/progression")).data,
    },
  ],
  schema,
  shape: ([streak, progress]) => {
    const days = (streak as { days?: unknown } | undefined)?.days;
    const multiplier = (streak as { multiplier?: unknown } | undefined)?.multiplier;
    const achievements = (progress as { achievements?: unknown } | undefined)?.achievements;
    return {
      streak_days: typeof days === "number" ? days : 0,
      streak_multiplier: typeof multiplier === "number" ? multiplier : 1,
      achievements: typeof achievements === "number" ? achievements : 0,
    };
  },
};
