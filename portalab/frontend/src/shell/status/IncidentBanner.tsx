import { useT } from "../../i18n/hooks/useT";
import { useDismissed, useOpenIncidents } from "./portalStatus";
import { StatusBanner } from "./StatusBanner";

const RANK: Record<string, number> = { critical: 0, major: 1, minor: 2 };

/**
 * Incident banner (027): an open incident announced « as a banner » (when declared, or by its service's
 * alerting rule) shows across the portal until it is resolved — the most severe first: its severity and
 * step, its title and its latest news, a link to it. Each member may close it; it comes back
 * if it gets more severe.
 */
export function IncidentBanner() {
  const t = useT();
  const [closed, close] = useDismissed("portalab.incident.dismissed");
  const open = useOpenIncidents();
  const shown = (Array.isArray(open.data) ? open.data : [])
    .filter((i) => i.banner && i.state !== "resolved" && !closed.includes(`${i.id}:${i.severity}`))
    .sort((a, b) => (RANK[a.severity] ?? 3) - (RANK[b.severity] ?? 3));
  const first = shown[0];
  if (!first) return null;
  const news = first.updates.at(-1)?.message;
  return (
    <StatusBanner
      tone="incident"
      icon="alert"
      eyebrow={[
        t("support:banner.incident"),
        t(`support:severity.${first.severity}`),
        t(`support:state.${first.state}`),
      ]}
      title={first.title}
      text={news && news !== first.title ? news : first.summary}
      starts={first.created_at}
      details={`/incidents/${first.id}`}
      onClose={() => close(`${first.id}:${first.severity}`)}
    />
  );
}
