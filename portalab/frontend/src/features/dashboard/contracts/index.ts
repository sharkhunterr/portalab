import { useQueries } from "@tanstack/react-query";
import { useMemo } from "react";
import { ApiError } from "../../../state/regions";
import { progression } from "./progression";
import { recentlyAdded } from "./recentlyAdded";
import { statistics } from "./statistics";
import type { Contract } from "./types";
import { watching } from "./watching";
import { isWidgetData, widgetData } from "./widgetData";

export type { Contract } from "./types";

/**
 * 028 (US6, R26): the data contracts offered to packs' widgets — the same keys as the server's catalog
 * (``WIDGET_CONTRACTS``), which refuses any other at the analysis and lists them at the Review step.
 */
export const CONTRACTS: Record<string, Contract> = Object.fromEntries(
  [progression, watching, recentlyAdded, statistics].map((contract) => [contract.key, contract]),
);

/** A contract the portal offers: the catalog's, or a dashboard widget's data (``widget:<key>``). */
export function contractOf(key: string): Contract | undefined {
  return CONTRACTS[key] ?? (isWidgetData(key) ? (widgetData(key) as Contract) : undefined);
}

export type ContractState = { state: "forbidden" | "error" | "loading" };
export type ContractValue = unknown | ContractState;

/** A contract's value from what its routes answered: its schema's fields only, or ``error``. */
export function project(contract: Contract, answers: unknown[]): ContractValue {
  const parsed = contract.schema.safeParse(contract.shape(answers));
  return parsed.success ? parsed.data : { state: "error" };
}

/**
 * What a widget is handed: for each contract it declared (and only those the portal offers), its projected
 * value — or ``forbidden`` when this member may not read it (never read then), ``loading``, ``error``.
 */
export function useContracts(
  declared: readonly string[],
  forbidden: readonly string[],
): Record<string, ContractValue> {
  const wanted = declared.filter((key, index) => contractOf(key) && declared.indexOf(key) === index);
  const readable = wanted.filter((key) => !forbidden.includes(key));
  const plan = readable.flatMap((key) =>
    (contractOf(key) as Contract).sources.map((source) => ({ key, source })),
  );
  const results = useQueries({
    queries: plan.map(({ key, source }) => ({
      queryKey: source.queryKey,
      queryFn: source.queryFn,
      retry: false,
      staleTime: 30_000,
      refetchInterval: (contractOf(key) as Contract).refreshS * 1000,
    })),
  });
  const signature = results.map((r) => `${r.status}:${r.dataUpdatedAt}`).join("|");
  // biome-ignore lint/correctness/useExhaustiveDependencies: recomputed when an answer changes
  return useMemo(() => {
    const out: Record<string, ContractValue> = {};
    for (const key of wanted) {
      if (!readable.includes(key)) {
        out[key] = { state: "forbidden" };
        continue;
      }
      const mine = plan
        .map((step, index) => ({ step, result: results[index] }))
        .filter((x) => x.step.key === key);
      const failed = mine.find((x) => x.result?.isError);
      if (failed) {
        const status = failed.result?.error instanceof ApiError ? failed.result.error.status : 0;
        out[key] = { state: status === 401 || status === 403 ? "forbidden" : "error" };
      } else if (mine.some((x) => !x.result?.isSuccess)) {
        out[key] = { state: "loading" };
      } else {
        out[key] = project(
          contractOf(key) as Contract,
          mine.map((x) => x.result?.data),
        );
      }
    }
    return out;
  }, [signature, wanted.join(","), forbidden.join(",")]);
}
