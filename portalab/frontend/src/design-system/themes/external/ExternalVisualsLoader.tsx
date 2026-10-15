import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../../../api/client";
import { type ExternalElement, installElements, uninstallScope } from "./external";

export const ACTIVE_VISUALS_KEY = ["visuals", "active"] as const;

/**
 * issue 1: loads the published visual packs once signed in — their stylesheets linked, their GPU looks
 * registered — and again when what is published changes (``stamp``). Nothing is shown when none is.
 */
export function ExternalVisualsLoader() {
  const active = useQuery({
    queryKey: ACTIVE_VISUALS_KEY,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () =>
      (await api.GET("/api/v1/visuals/active")).data as unknown as {
        elements: ExternalElement[];
        stamp: string;
      },
  });
  const stamp = active.data?.stamp;
  // biome-ignore lint/correctness/useExhaustiveDependencies: installed again only when the packs change
  useEffect(() => {
    if (active.data) void installElements(active.data.elements, "live");
  }, [stamp]);
  useEffect(() => () => uninstallScope("live"), []);
  return null;
}
