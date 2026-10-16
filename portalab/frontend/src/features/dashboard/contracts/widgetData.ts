import { z } from "zod";
import { api } from "../../../api/client";
import type { Contract } from "./types";

/** ``widget:<key>``: any dashboard widget's own data — what that widget shows this member (028, US6). */
export const WIDGET_DATA = "widget:";
const KEY = /^[a-z0-9][a-z0-9_.:-]{1,95}$/;
/** what a widget's data may weigh when handed over (a widget shows a page of things, never a library) */
const MAX_BYTES = 256 * 1024;

export function isWidgetData(key: string): boolean {
  const widget = key.slice(WIDGET_DATA.length);
  return (
    key.startsWith(WIDGET_DATA) && KEY.test(widget) && widget.includes(".") && !widget.startsWith("pack.")
  );
}

const schema = z.union([
  z.object({ state: z.literal("forbidden") }),
  z.object({
    state: z.enum(["available", "partial", "stale", "no-data"]),
    as_of: z.string().nullable(),
    data: z.unknown(),
  }),
]);

/** The contract reading one widget's data through the dashboard (its permission, its purchase when sold). */
export function widgetData(key: string): Contract<z.infer<typeof schema>> {
  const widget = key.slice(WIDGET_DATA.length);
  return {
    key,
    permission: "",
    refreshS: 60,
    sources: [
      {
        queryKey: ["widget", widget, "contract"],
        queryFn: async () =>
          (await api.GET("/api/v1/widgets/{key}/data", { params: { path: { key: widget } } })).data,
      },
    ],
    schema,
    shape: ([payload]) => {
      const answer = (payload ?? {}) as { state?: string; as_of?: string | null; data?: unknown };
      if (answer.state === "unauthorized") return { state: "forbidden" };
      if (!["available", "partial", "stale", "no-data"].includes(String(answer.state))) return null;
      const data = answer.data ?? null;
      if (JSON.stringify(data).length > MAX_BYTES) return null;
      return { state: answer.state, as_of: answer.as_of ?? null, data };
    },
  };
}
