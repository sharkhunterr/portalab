import type { NotificationTone, Severity } from "../../design-system/components/Notification";
import type { NotificationItem } from "./api";

/**
 * Alert vs notification presentation (spec 010 T014): an alert is urgent (critical → ``critical``, high →
 * ``warning``), a notification is information. Meaning is carried by icon + text, never by color alone, and
 * presentation preferences (position, style, theme) change appearance only.
 */
export function severityOf(item: Pick<NotificationItem, "kind" | "priority">): Severity {
  if (item.kind === "alert") return item.priority === "critical" ? "critical" : "warning";
  return item.priority === "critical" || item.priority === "high" ? "warning" : "info";
}

/** 027: how a notification looks — a colour family, an icon and a short badge from its category. */
const CATEGORY_LOOK: Array<[prefix: string, icon: string, tone: NotificationTone | null, badge: string]> = [
  ["gamification", "trophy", "reward", "reward"],
  ["media.available", "check", "success", "media"],
  ["media", "film", null, "media"],
  ["support", "lifebuoy", null, "support"],
  ["system.health", "alert", null, "system"],
  ["system.maintenance", "wrench", "warning", "system"],
  ["account.security", "shield", "warning", "security"],
  ["communications", "newspaper", null, "news"],
  ["news", "newspaper", null, "news"],
  ["marketplace", "shop", "reward", "shop"],
  ["community", "users", null, "community"],
  ["campaigns", "sparkles", "reward", "event"],
  ["calendar", "calendar", null, "event"],
];

export function lookOf(item: Pick<NotificationItem, "kind" | "priority" | "category">): {
  tone: NotificationTone;
  icon: string;
  badge: string | null;
} {
  const severity = severityOf(item);
  const category = item.category ?? "";
  const match = CATEGORY_LOOK.find(([prefix]) => category === prefix || category.startsWith(`${prefix}.`));
  if (item.kind === "alert" || !match) {
    return {
      tone: severity,
      icon: match?.[1] ?? (item.kind === "alert" ? "alert" : "bell"),
      badge: match?.[3] ?? null,
    };
  }
  return { tone: severity !== "info" ? severity : (match[2] ?? "info"), icon: match[1], badge: match[3] };
}
