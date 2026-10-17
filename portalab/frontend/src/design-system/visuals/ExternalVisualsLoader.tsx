import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../../api/client";
import { connectStream } from "../../api/stream";
import { type ExternalElement, installElements, preloadFiles, setWithheld, uninstallScope } from "./registry";
import { LOOKS_KEY } from "./vocabulary";

export const ACTIVE_VISUALS_KEY = ["visuals", "active"] as const;

/**
 * 028: loads the live visual packs once signed in — their stylesheets guarded and adopted, their GPU looks
 * registered — and again when the registry changes: the live event ``visuals.changed`` (a pack switched off
 * reaches every member within moments), else once a minute. Nothing is shown when none is live.
 */
export function ExternalVisualsLoader({ live = typeof EventSource !== "undefined" }: { live?: boolean }) {
  const client = useQueryClient();
  const active = useQuery({
    queryKey: ACTIVE_VISUALS_KEY,
    retry: false,
    staleTime: 30_000,
    refetchInterval: 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/visuals/active")).data as unknown as {
        elements: ExternalElement[];
        epoch: number;
        withheld?: Record<string, string[]>;
      },
  });
  useEffect(() => {
    if (!live) return;
    const handle = connectStream({
      topics: ["visuals.changed"],
      onEvent: () => {
        void client.invalidateQueries({ queryKey: ACTIVE_VISUALS_KEY });
        void client.invalidateQueries({ queryKey: LOOKS_KEY }); // the looks one may name with them
      },
    });
    return () => handle.close();
  }, [live, client]);
  const epoch = active.data?.epoch;
  // biome-ignore lint/correctness/useExhaustiveDependencies: installed again only when the registry changes
  useEffect(() => {
    if (!active.data) return;
    const { elements, withheld } = active.data;
    setWithheld(withheld);
    // 028 (B2): all their files in one answer for this epoch, then installed (a file it lacks is read alone)
    void fetch(`/api/v1/visuals/live/${epoch}`, { credentials: "same-origin" })
      .then((response) => (response.ok ? response.json() : null))
      .catch(() => null)
      .then((data) => {
        preloadFiles((data?.files as Record<string, string> | undefined) ?? null);
        return installElements(elements, "live");
      });
  }, [epoch]);
  useEffect(() => () => uninstallScope("live"), []);
  return null;
}
