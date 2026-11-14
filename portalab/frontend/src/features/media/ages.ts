import { useQuery } from "@tanstack/react-query";

/**
 * Issue 434: the age ratings of the titles a page shows, asked in batches — every thumbnail asks its own,
 * one call carries a whole shelf (-1: an unrated title; unknown: no badge).
 */
type Waiting = Array<(age: number | null) => void>;
const pending = new Map<string, Waiting>();
let timer: ReturnType<typeof setTimeout> | null = null;
const BATCH = 100;

async function flush(): Promise<void> {
  timer = null;
  const ids = [...pending.keys()].slice(0, BATCH);
  const waiting = ids.map((id) => [id, pending.get(id) ?? []] as const);
  for (const id of ids) pending.delete(id);
  if (pending.size) timer = setTimeout(() => void flush(), 0);
  let ages: Record<string, number> = {};
  try {
    const response = await fetch(`/api/v1/media/ages?ids=${ids.join(",")}`, { credentials: "include" });
    if (response.ok) ages = ((await response.json()) as { ages: Record<string, number> }).ages ?? {};
  } catch {
    // no badge this time
  }
  for (const [id, resolvers] of waiting) for (const resolve of resolvers) resolve(ages[id] ?? null);
}

export function ageOf(id: string): Promise<number | null> {
  return new Promise((resolve) => {
    const waiting = pending.get(id) ?? [];
    waiting.push(resolve);
    pending.set(id, waiting);
    if (!timer) timer = setTimeout(() => void flush(), 15);
  });
}

/** One title's age rating (``undefined`` while asked; ``null`` unknown; -1 unrated). */
export function useAge(id: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: ["media", "age", id],
    enabled: enabled && Boolean(id),
    staleTime: 10 * 60_000,
    queryFn: () => ageOf(id as string),
  });
}
