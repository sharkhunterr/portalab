import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { DAY, isRunning, upcoming, useDismissed, useMaintenances } from "./portalStatus";
import { StatusBanner, useNow } from "./StatusBanner";

/**
 * Maintenance banner (027): a maintenance announced « as a banner » shows across the portal from the day
 * before until it ends — when it starts or ends from now, its title and details, the start and the end
 * apart, how far along it is while it runs, a link to the incidents page; each member may close it.
 */
export function MaintenanceBanner() {
  const t = useT();
  const format = useFormat();
  const now = useNow();
  const [closed, close] = useDismissed("portalab.maintenance.dismissed");
  const windows = useMaintenances();
  const first = upcoming(windows.data, DAY, now).find((m) => m.banner && !closed.includes(m.id));
  if (!first) return null;
  const running = isRunning(first, now);
  const start = Date.parse(first.starts_at);
  const end = Date.parse(first.ends_at);
  return (
    <StatusBanner
      tone={running ? "running" : "planned"}
      icon="wrench"
      eyebrow={[
        t(running ? "support:maintenance.running" : "support:maintenance.planned"),
        running
          ? t("support:banner.endsIn", { when: format.relative((end - now) / 1000) })
          : t("support:banner.startsIn", { when: format.relative((start - now) / 1000) }),
      ]}
      title={first.title}
      text={first.description}
      starts={first.starts_at}
      ends={first.ends_at}
      progress={running ? (now - start) / Math.max(1, end - start) : null}
      details="/incidents"
      onClose={() => close(first.id)}
    />
  );
}
