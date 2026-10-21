import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { AdminEmpty, AdminPage, AdminSection, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { isRunning, useMaintenances, useOpenIncidents } from "../../../shell/status/portalStatus";
import { StatusBanner, useNow } from "../../../shell/status/StatusBanner";
import "../admin.css";
import "./banners.css";

interface AnnouncementBanner {
  id: string;
  title: string;
  body: string;
  link: string | null;
  tone: "info" | "success" | "warning" | "critical";
  banner_until: string | null;
  dismissible: boolean;
  created_at: string;
}

const ICONS = { info: "megaphone", success: "sparkles", warning: "alert", critical: "alert" } as const;

/**
 * ``/admin/banners`` (admin reorganisation, trial): every banner across the portal right now, whatever put
 * it there — an announcement (or an automation's), an incident, a maintenance — drawn as members see it,
 * with where it comes from, until when, and the way to take it down or to its origin.
 */
export default function BannersAdmin() {
  const t = useT();
  const format = useFormat();
  const now = useNow();
  const client = useQueryClient();
  const announcements = useQuery({
    queryKey: ["announcements", "banners"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/announcements/banners")).data ?? []) as unknown as AnnouncementBanner[],
  });
  const incidents = useOpenIncidents();
  const maintenances = useMaintenances();
  const end = useMutation({
    mutationFn: async (id: string) =>
      api.POST("/api/v1/admin/announcements/{announcement_id}/end", {
        params: { path: { announcement_id: id } },
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["announcements"] });
      void client.invalidateQueries({ queryKey: ["admin", "notifications", "announcements"] });
    },
  });
  const shownIncidents = (Array.isArray(incidents.data) ? incidents.data : []).filter(
    (i) => i.banner && i.state !== "resolved",
  );
  const shownMaintenances = (maintenances.data ?? []).filter(
    (m) => m.banner && m.status !== "cancelled" && Date.parse(m.ends_at) > now,
  );
  const rows = announcements.data ?? [];
  const none = !rows.length && !shownIncidents.length && !shownMaintenances.length;
  return (
    <AdminPage icon="megaphone" title={t("admin:banners.title")} description={t("admin:banners.subtitle")}>
      <AdminSection title={t("admin:banners.now")} icon="megaphone" span="full">
        {none ? (
          <AdminEmpty
            icon="megaphone"
            title={t("admin:banners.none")}
            action={
              <Button asChild variant="secondary">
                <Link to="/admin/announcements">{t("admin:banners.announce")}</Link>
              </Button>
            }
          />
        ) : null}
        <ul className="banners-admin">
          {rows.map((row) => (
            <li key={`a-${row.id}`} className="banners-admin__item">
              <StatusBanner
                tone={row.tone}
                icon={ICONS[row.tone] ?? "megaphone"}
                eyebrow={[t("notifications:banner.announcement")]}
                title={row.title}
                text={row.body ? row.body.split("\n")[0] : null}
                details={row.link}
                detailsLabel={t("notifications:banner.more")}
              />
              <div className="banners-admin__meta">
                <StatusBadge tone="info">{t("admin:banners.source.announcement")}</StatusBadge>
                <span className="admin-muted">
                  {row.banner_until
                    ? t("admin:announce.bannerLiveUntil", { date: format.dateTime(row.banner_until) })
                    : t("admin:announce.bannerLive")}
                  {" · "}
                  {row.dismissible ? t("admin:banners.closable") : t("admin:announce.kept")}
                </span>
                <Button variant="secondary" disabled={end.isPending} onClick={() => end.mutate(row.id)}>
                  <Icon name="close" size={14} />
                  {t("admin:announce.endBanner")}
                </Button>
              </div>
            </li>
          ))}
          {shownIncidents.map((incident) => (
            <li key={`i-${incident.id}`} className="banners-admin__item">
              <StatusBanner
                tone="incident"
                icon="alert"
                eyebrow={[t("support:banner.incident"), t(`support:severity.${incident.severity}`)]}
                title={incident.title}
                text={incident.updates.at(-1)?.message ?? incident.summary}
                starts={incident.created_at}
              />
              <div className="banners-admin__meta">
                <StatusBadge tone="bad">{t("admin:banners.source.incident")}</StatusBadge>
                <span className="admin-muted">{t("admin:banners.untilResolved")}</span>
                <Button asChild variant="secondary">
                  <Link to="/admin/incidents">
                    <Icon name="chevron-right" size={14} />
                    {t("admin:banners.manage")}
                  </Link>
                </Button>
              </div>
            </li>
          ))}
          {shownMaintenances.map((window) => {
            const running = isRunning(window, now);
            return (
              <li key={`m-${window.id}`} className="banners-admin__item">
                <StatusBanner
                  tone={running ? "running" : "planned"}
                  icon="wrench"
                  eyebrow={[t(running ? "support:maintenance.running" : "support:maintenance.planned")]}
                  title={window.title}
                  text={window.description}
                  starts={window.starts_at}
                  ends={window.ends_at}
                />
                <div className="banners-admin__meta">
                  <StatusBadge tone="warn">{t("admin:banners.source.maintenance")}</StatusBadge>
                  <span className="admin-muted">
                    {running
                      ? t("admin:banners.untilEnd")
                      : t("admin:banners.fromDayBefore", {
                          date: format.dateTime(
                            new Date(Date.parse(window.starts_at) - 86_400_000).toISOString(),
                          ),
                        })}
                  </span>
                  <Button asChild variant="secondary">
                    <Link to="/admin/maintenance">
                      <Icon name="chevron-right" size={14} />
                      {t("admin:banners.manage")}
                    </Link>
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      </AdminSection>
    </AdminPage>
  );
}
