import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";

/** Pieces shared by the incidents page and the incidents widget (027). Severity and state are always
 * written, never shown by colour alone. */
export const STATES = ["investigating", "identified", "monitoring", "resolved"] as const;
export const SEVERITY_ICONS: Record<string, string> = { minor: "info", major: "warning", critical: "alert" };
const STATE_ICONS: Record<string, string> = {
  investigating: "search",
  identified: "target",
  monitoring: "eye",
  resolved: "check",
};

/** How long it has lasted (or lasted): minutes, hours or days. */
export function useLasting() {
  const t = useT();
  return (from: string, to?: string | null) => {
    const minutes = Math.max(1, Math.round(((to ? Date.parse(to) : Date.now()) - Date.parse(from)) / 60_000));
    if (minutes < 60) return t("support:incident.minutes", { count: minutes });
    const hours = Math.round(minutes / 60);
    if (hours < 48) return t("support:incident.hours", { count: hours });
    return t("support:incident.days", { count: Math.round(hours / 24) });
  };
}

export function SeverityBadge({ severity }: { severity: string }) {
  const t = useT();
  return (
    <span className="incident-severity" data-severity={severity}>
      <Icon name={SEVERITY_ICONS[severity] ?? "alert"} size={12} />
      {t(`support:severity.${severity}`)}
    </span>
  );
}

/** The four steps of an incident, the current one marked — each step in its own colour (027), also named. */
export function StateSteps({ state, compact = false }: { state: string; compact?: boolean }) {
  const t = useT();
  const reached = STATES.indexOf(state as (typeof STATES)[number]);
  return (
    <ol
      className="incident-steps"
      data-compact={compact || undefined}
      aria-label={t(`support:state.${state}`)}
    >
      {STATES.map((step, index) => (
        <li
          key={step}
          data-step={step}
          data-done={index < reached || state === "resolved" || undefined}
          data-current={index === reached || undefined}
        >
          <span className="incident-steps__dot" aria-hidden="true">
            <Icon name={STATE_ICONS[step] ?? "check"} size={compact ? 10 : 12} />
          </span>
          {compact ? null : <span className="incident-steps__label">{t(`support:state.${step}`)}</span>}
        </li>
      ))}
    </ol>
  );
}
