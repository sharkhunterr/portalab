import type { Severity } from "../../design-system/components/Notification";
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
