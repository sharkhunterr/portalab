import type { NavCommand } from "../nav/NavigationProvider";

/**
 * Command registry (spec 004 T028; R9): destinations and actions from the server-filtered navigation view
 * (only permitted commands exist) plus local actions registered by the shell. Matching is a small fuzzy
 * subsequence score over the label and keywords.
 */
export interface Command {
  id: string;
  label: string;
  keywords: string[];
  route?: string | null;
  run?: () => void;
  sensitive?: boolean;
}

export function score(query: string, text: string): number {
  const q = query.trim().toLowerCase();
  const t = text.toLowerCase();
  if (!q) return 1;
  if (t.startsWith(q)) return 100 - t.length / 100;
  if (t.includes(q)) return 50 - t.indexOf(q);
  let position = 0;
  let gaps = 0;
  for (const char of q) {
    const found = t.indexOf(char, position);
    if (found < 0) return 0;
    gaps += found - position;
    position = found + 1;
  }
  return Math.max(1, 20 - gaps);
}

export function rank(commands: readonly Command[], query: string, limit = 20): Command[] {
  return commands
    .map((command) => ({
      command,
      score: Math.max(score(query, command.label), ...command.keywords.map((k) => score(query, k) * 0.8)),
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.command.label.localeCompare(b.command.label))
    .slice(0, limit)
    .map((item) => item.command);
}

export function fromNavigation(
  commands: readonly NavCommand[],
  label: (key: string) => string,
  actions: Record<string, () => void>,
): Command[] {
  const seen = new Set<string>();
  const out: Command[] = [];
  for (const command of commands) {
    if (seen.has(command.key)) continue;
    seen.add(command.key);
    const run = command.action_id ? actions[command.action_id] : undefined;
    if (command.action_id && !run) continue; // an action this client does not know is not offered
    out.push({
      id: command.key,
      label: label(command.label_key),
      keywords: command.keywords ?? [],
      route: command.route ?? null,
      ...(run ? { run } : {}),
      sensitive: command.sensitivity === "sensitive" || Boolean(command.confirmation_required),
    });
  }
  return out;
}
