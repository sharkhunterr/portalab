import { z } from "zod";
import { api } from "../../../api/client";
import type { Contract } from "./types";

const schema = z.object({
  level: z.number().int(),
  xp: z.number(),
  level_floor: z.number(),
  next_level_at: z.number().nullable(),
  coins: z.number(),
  contribution: z.number(),
});

/** ``me.progression``: the member's level, experience towards the next one, coins and contribution. */
export const progression: Contract<z.infer<typeof schema>> = {
  key: "me.progression",
  permission: "users.self.manage",
  refreshS: 60,
  // the query the progression page and the header share
  sources: [
    {
      queryKey: ["gamification", "progression"],
      queryFn: async () => (await api.GET("/api/v1/me/progression")).data,
    },
  ],
  schema,
  shape: ([progress]) => progress,
};
