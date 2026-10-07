import type { useFormat } from "../../i18n/format/useFormat";
import type { Translate } from "../../i18n/hooks/useT";
import type { Catalog, ConditionNode, Filter, Trigger } from "./api";

/**
 * Words for automations (027): events, actions, conditions and triggers as sentences an administrator
 * reads — the translated label when the catalog has one, else the server's description, else the key
 * made readable (« service.outage_lasting » → « Service · outage lasting »).
 */
export function maybe(t: Translate, key: string, fallback: string): string {
  const text = t(key);
  return text === key.split(":").slice(1).join(":") ? fallback : text;
}

export function humanize(name: string): string {
  const [domain = "", ...rest] = name.split(".");
  const tail = rest.join(" ").replaceAll("_", " ");
  const head = domain.replaceAll("_", " ");
  return tail ? `${head.charAt(0).toUpperCase()}${head.slice(1)} · ${tail}` : head;
}

export function eventLabel(t: Translate, name: string | null | undefined, catalog?: Catalog): string {
  if (!name) return "—";
  return maybe(
    t,
    `automations:event.${name}`,
    catalog?.triggers.event_descriptions?.[name] ?? humanize(name),
  );
}

export function actionLabel(t: Translate, key: string, catalog?: Catalog): string {
  const description = catalog?.actions.find((a) => a.key === key)?.description;
  return maybe(t, `automations:actionType.${key}`, description ?? humanize(key));
}

export function conditionLabel(t: Translate, key: string, catalog?: Catalog): string {
  const description = catalog?.conditions.find((c) => c.key === key)?.description;
  return maybe(t, `automations:condition.${key}`, description ?? humanize(key));
}

export function paramLabel(t: Translate, name: string): string {
  return maybe(t, `automations:param.${name}`, name.replaceAll("_", " "));
}

export const ACTION_ICONS: Record<string, string> = {
  "communication.produce": "bell",
  "incident.create": "alert",
  "ticket.create": "ticket",
  "approval.request": "check",
  "ai.invoke": "bot",
  "automation.trigger": "zap",
  "award.coins": "coins",
  "award.xp": "star",
  "award.contribution": "handshake",
  "reward.unlock": "trophy",
  "connector.action": "plug",
  "connector.sync": "sync",
  "content.publish": "newspaper",
};

export const TRIGGER_ICONS: Record<string, string> = {
  event: "zap",
  relative: "hourglass",
  recurring: "calendar",
  at: "clock",
};

const OPS: Record<Filter["op"], string> = {
  eq: "=",
  ne: "≠",
  in: "∈",
  gt: ">",
  gte: "≥",
  lt: "<",
  lte: "≤",
  contains: "∋",
};

/** 027: service ids read as the services' names wherever a rule shows them. */
export const serviceNames: { current: Map<string, string> } = { current: new Map() };

export function readable(value: unknown): string {
  const one = (v: unknown) => serviceNames.current.get(String(v)) ?? String(v ?? "");
  return Array.isArray(value) ? value.map(one).join(", ") : one(value);
}

export function filterText(t: Translate, filter: Filter): string {
  const value = readable(filter.value);
  return `${paramLabel(t, filter.field)} ${OPS[filter.op] ?? filter.op} ${value}`;
}

/** « When a service has been down for a while (minutes = 10) », « Every Monday at 09:00 »… */
export function triggerSummary(
  t: Translate,
  trigger: Trigger | null | undefined,
  catalog?: Catalog,
  format?: ReturnType<typeof useFormat>,
): string {
  if (!trigger) return "—";
  const filters = (trigger.filter ?? []).map((f) => filterText(t, f)).join(" · ");
  const suffix = filters ? ` (${filters})` : "";
  switch (trigger.kind) {
    case "event":
      return t("automations:when.event", { event: eventLabel(t, trigger.event_type, catalog) }) + suffix;
    case "relative":
      return (
        t("automations:when.relative", {
          minutes: Math.abs(trigger.offset_minutes ?? 0),
          direction: (trigger.offset_minutes ?? 0) < 0 ? "before" : "after",
          field: paramLabel(t, trigger.reference ?? ""),
          event: eventLabel(t, trigger.event_type, catalog),
        }) + suffix
      );
    case "at":
      return t("automations:when.at", {
        date: trigger.at ? (format ? format.dateTime(trigger.at) : trigger.at) : "—",
      });
    case "recurring": {
      const s = trigger.schedule;
      if (!s) return "—";
      if (s.frequency === "weekly")
        return t("automations:when.weekly", {
          day: t(`automations:weekday.${s.weekday ?? 0}`),
          time: s.time,
        });
      if (s.frequency === "monthly") return t("automations:when.monthly", { day: s.day ?? 1, time: s.time });
      return t("automations:when.daily", { time: s.time });
    }
    default:
      return "—";
  }
}

/** The leaves of a condition tree and how they combine — or ``null`` when the tree is deeper (shown raw). */
export function flatConditions(
  node: ConditionNode | null | undefined,
): { mode: "all" | "any"; leaves: Array<{ leaf: string; params: Record<string, unknown> }> } | null {
  if (!node) return { mode: "all", leaves: [] };
  if (node.leaf) return { mode: "all", leaves: [{ leaf: node.leaf, params: node.params ?? {} }] };
  const children = node.all_of ?? node.any_of;
  if (!children || children.some((c) => !c.leaf)) return null;
  return {
    mode: node.any_of ? "any" : "all",
    leaves: children.map((c) => ({ leaf: c.leaf as string, params: c.params ?? {} })),
  };
}

export function paramValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
