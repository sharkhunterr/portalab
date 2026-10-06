import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";

interface Maintenance {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  status: string;
  banner?: boolean;
}

const DAY = 86_400_000;
const DISMISSED = "portalab.maintenance.dismissed";

function dismissed(): string[] {
  try {
    return JSON.parse(window.localStorage.getItem(DISMISSED) ?? "[]") as string[];
  } catch {
    return [];
  }
}

/**
 * Maintenance banner (027): a maintenance announced « as a banner » shows across the portal from the day
 * before until it ends — when it starts and ends, a link to the incidents page; each member may close it.
 */
export function MaintenanceBanner() {
  const t = useT();
  const format = useFormat();
  const [closed, setClosed] = useState<string[]>(dismissed);
  const windows = useQuery({
    queryKey: ["maintenance", "banner"],
    retry: false,
    refetchInterval: 5 * 60_000,
    queryFn: async () =>
      ((await api.GET("/api/v1/maintenance")).data as unknown as { items: Maintenance[] }).items ?? [],
  });
  const now = Date.now();
  const shown = (windows.data ?? []).filter(
    (m) =>
      m.banner &&
      m.status !== "cancelled" &&
      Date.parse(m.ends_at) > now &&
      Date.parse(m.starts_at) - now < DAY &&
      !closed.includes(m.id),
  );
  const first = shown[0];
  if (!first) return null;
  const running = Date.parse(first.starts_at) <= now;
  const close = () => {
    const next = [...closed, first.id].slice(-20);
    setClosed(next);
    try {
      window.localStorage.setItem(DISMISSED, JSON.stringify(next));
    } catch {
      // no storage: closed for this visit only
    }
  };
  return (
    <div className="maintenance-banner" role="status" data-running={running || undefined}>
      <Icon name="wrench" size={18} />
      <span>
        <strong>{t(running ? "support:maintenance.running" : "support:maintenance.planned")}</strong> ·{" "}
        {first.title} · {format.dateTime(first.starts_at)} → {format.dateTime(first.ends_at)}
      </span>
      <Link to="/incidents">{t("support:maintenance.details")}</Link>
      <button
        type="button"
        className="maintenance-banner__close"
        onClick={close}
        aria-label={t("support:maintenance.close")}
      >
        <Icon name="close" size={16} />
      </button>
    </div>
  );
}
