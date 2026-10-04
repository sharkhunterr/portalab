import type { Translate } from "../../../i18n/hooks/useT";
import { useT } from "../../../i18n/hooks/useT";

/**
 * Ticket state and priority badges (027 T095): the label is always text; the tone only reinforces it.
 * Workflows may define their own states — an unknown key shows the server's label (or the key itself).
 */
const STATE_TONE: Record<string, string> = {
  open: "open",
  in_progress: "active",
  waiting_user: "waiting",
  resolved: "done",
  closed: "closed",
  cancelled: "closed",
};

export function stateLabel(t: Translate, state: string, serverLabel?: string | null): string {
  const label = t(`support:tstate.${state}`);
  return label === `tstate.${state}` ? (serverLabel ?? state) : label;
}

export function isActive(state: string): boolean {
  return !["resolved", "closed", "cancelled"].includes(state);
}

export function StateBadge({ state, label }: { state: string; label?: string | null }) {
  const t = useT();
  return (
    <span className="ds-badge support-state" data-tone={STATE_TONE[state] ?? "open"}>
      {stateLabel(t, state, label)}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  const t = useT();
  return (
    <span className="ds-badge support-priority" data-priority={priority}>
      {t(`support:priority.${priority}`)}
    </span>
  );
}
