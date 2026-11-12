/**
 * Issue 392 — what an archive brought into a new portal may be: its blocks (the backend's
 * ``backup/blocks.py``), each ticked or not. Ticking one ticks what it needs; unticking one unticks what
 * needs it. Every block ticked is the whole portal, as an import without a choice.
 */
export interface OfferedBlock {
  key: string;
  needs: string[];
  counts: Record<string, number>;
}

export const BLOCK_ICONS: Record<string, string> = {
  settings: "settings",
  members: "users",
  services: "server",
  notifications: "bell",
  media: "film",
  statistics: "chart",
  automations: "zap",
  content: "book",
  gamification: "trophy",
  marketplace: "store",
  look: "palette",
  plugins: "plug",
  assistant: "bot",
  health: "activity",
  history: "scroll",
};

function needsOf(blocks: readonly OfferedBlock[], key: string): string[] {
  return blocks.find((b) => b.key === key)?.needs ?? [];
}

/** The chosen blocks once ``key`` is ticked (with what it needs) or unticked (with what needs it). */
export function toggled(
  blocks: readonly OfferedBlock[],
  chosen: ReadonlySet<string>,
  key: string,
  on: boolean,
): Set<string> {
  const next = new Set(chosen);
  const pending = [key];
  while (pending.length) {
    const current = pending.pop() as string;
    if (on) {
      if (next.has(current)) continue;
      next.add(current);
      pending.push(...needsOf(blocks, current));
    } else {
      if (!next.has(current)) continue;
      next.delete(current);
      pending.push(...blocks.filter((b) => b.needs.includes(current)).map((b) => b.key));
    }
  }
  return next;
}

/** The chosen blocks that need ``key`` (why it cannot be unticked alone). */
export function neededBy(
  blocks: readonly OfferedBlock[],
  chosen: ReadonlySet<string>,
  key: string,
): string[] {
  return blocks.filter((b) => chosen.has(b.key) && b.needs.includes(key)).map((b) => b.key);
}

/** What the import is asked for: nothing when every block is ticked (the whole portal), else the blocks. */
export function requested(
  blocks: readonly OfferedBlock[],
  chosen: ReadonlySet<string>,
): string[] | undefined {
  return blocks.every((b) => chosen.has(b.key))
    ? undefined
    : blocks.map((b) => b.key).filter((k) => chosen.has(k));
}
