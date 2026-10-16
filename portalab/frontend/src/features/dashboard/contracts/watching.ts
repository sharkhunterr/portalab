import { z } from "zod";
import { api } from "../../../api/client";
import { type Contract, LIST_LIMIT } from "./types";

const schema = z.object({
  items: z
    .array(z.object({ title: z.string(), kind: z.string(), percent: z.number().min(0).max(100) }))
    .max(LIST_LIMIT),
});

/** ``me.watching``: what the member is watching or reading — titles, kinds and how far they are. */
export const watching: Contract<z.infer<typeof schema>> = {
  key: "me.watching",
  permission: "users.self.manage",
  refreshS: 120,
  sources: [
    {
      queryKey: ["media", "continue"],
      queryFn: async () => (await api.GET("/api/v1/me/media/continue")).data ?? [],
    },
  ],
  schema,
  shape: ([rows]) => ({
    items: (Array.isArray(rows) ? rows : []).slice(0, LIST_LIMIT).map((row) => {
      const item = row as { title?: unknown; kind?: unknown; percent?: unknown };
      const percent = Number(item.percent ?? 0);
      return {
        title: String(item.title ?? ""),
        kind: String(item.kind ?? ""),
        percent: Math.max(0, Math.min(100, Number.isFinite(percent) ? percent : 0)),
      };
    }),
  }),
};
