import type { Operation } from "./tuning";

/** An operation of the journal, or (issue 258) a series of the same one told as one line. */
export interface JournalLine extends Operation {
  /** how many operations it stands for */
  count: number;
  /** when the first of them happened (the line's own date is the latest's) */
  since: string;
}

/**
 * Issue 258: the same gain made again and again (the radio's quarters of an hour, a page of the same quest)
 * told once (issue 261: not a sitting — a film, an episode, a session of radio is a line of its own) — one
 * line per member, value, source, rule and title in a day, where the latest of them is, with
 * their amounts and bonuses added up; its balance and level are the latest's.
 */
const SITTINGS = new Set(["radio", "episode", "movie", "live", "book", "audiobook", "music", "game"]);

export function repeats(rows: Operation[]): JournalLine[] {
  const lines: JournalLine[] = [];
  const at = new Map<string, number>();
  for (const row of rows) {
    // issue 261: a sitting (a film, an episode, a session of radio) or a work is its own gain, with its own
    // reckoning — one line each, never added up
    if (row.work || row.reckoning?.field || SITTINGS.has(row.source)) {
      lines.push({ ...row, count: 1, since: row.occurred_at });
      continue;
    }
    const key = [
      row.user_id,
      row.value,
      row.kind,
      row.source,
      row.label ?? "",
      row.title ?? "",
      row.reason ?? "",
      row.other ?? "",
      Math.sign(row.delta),
      new Date(row.occurred_at).toDateString(),
    ].join("|");
    const index = at.get(key);
    const line = index === undefined ? undefined : lines[index];
    if (!line) {
      at.set(key, lines.length);
      lines.push({ ...row, bonuses: [...(row.bonuses ?? [])], count: 1, since: row.occurred_at });
      continue;
    }
    // the journal comes the latest first: what follows happened before
    line.delta += row.delta;
    line.count += 1;
    line.since = row.occurred_at;
    line.level_up = line.level_up || row.level_up;
    const bonuses = line.bonuses ?? [];
    for (const bonus of row.bonuses ?? []) {
      const kept = bonuses.find((b) => b.source === bonus.source);
      if (!kept) bonuses.push({ ...bonus });
      else {
        kept.amount = Math.round((kept.amount + bonus.amount) * 10) / 10;
        if (kept.factor !== bonus.factor) kept.factor = null; // not the same all along: no single one to say
      }
    }
    line.bonuses = bonuses;
  }
  return lines;
}
