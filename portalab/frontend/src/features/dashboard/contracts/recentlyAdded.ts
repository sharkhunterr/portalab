import { z } from "zod";
import { api } from "../../../api/client";
import { type Contract, LIST_LIMIT } from "./types";

const schema = z.object({
  items: z
    .array(z.object({ title: z.string(), kind: z.string(), year: z.number().int().nullable() }))
    .max(LIST_LIMIT),
});

/** ``media.recently_added``: what arrived in the library lately — titles, kinds and years. */
export const recentlyAdded: Contract<z.infer<typeof schema>> = {
  key: "media.recently_added",
  permission: "media.read",
  refreshS: 600,
  // the discovery shelf « new » the media pages show
  sources: [
    {
      queryKey: ["media", "shelf", "new"],
      queryFn: async () =>
        (await api.GET("/api/v1/media/discovery/{shelf}", { params: { path: { shelf: "new" } } })).data,
    },
  ],
  schema,
  shape: ([shelf]) => ({
    items: ((shelf as { items?: unknown[] } | undefined)?.items ?? []).slice(0, LIST_LIMIT).map((row) => {
      const item = row as { title?: unknown; kind?: unknown; year?: unknown };
      return {
        title: String(item.title ?? ""),
        kind: String(item.kind ?? ""),
        year: typeof item.year === "number" ? Math.trunc(item.year) : null,
      };
    }),
  }),
};
