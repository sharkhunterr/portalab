import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { AdminGrid, AdminPage, AdminStats } from "../../../design-system/admin/AdminKit";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { NewslettersPanel } from "../../news/NewsChannels";
import { Deliveries, type Status } from "./AnnouncementsAdmin";
import { DigestDefault, EmailSettings } from "./EmailSettings";
import "../admin.css";

/**
 * ``/admin/newsletters`` (admin reorganisation, trial): everything that goes out by e-mail in one page — the
 * automatic newsletters, the default digest, how the e-mails are sent (with a test) and how they went.
 */
export default function NewslettersAdmin() {
  const t = useT();
  const format = useFormat();
  const status = useQuery({
    queryKey: ["admin", "notifications", "status"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/admin/notifications/status")).data as unknown as Status,
  });
  const total = (s: string) =>
    (status.data?.deliveries ?? []).filter((d) => d.status === s).reduce((a, d) => a + d.count, 0);
  return (
    <AdminPage
      icon="message"
      title={t("admin:newsletters.title")}
      description={t("admin:newsletters.subtitle")}
    >
      <AdminStats
        label={t("admin:announce.deliveries")}
        stats={[
          {
            key: "email",
            label: t("admin:announce.email"),
            value: status.data?.email_enabled ? t("admin:announce.on") : t("admin:announce.off"),
            icon: "message",
            tone: status.data?.email_enabled ? "ok" : "neutral",
          },
          {
            key: "sent",
            label: t("admin:announce.sentCount"),
            value: format.number(total("sent") + total("delivered")),
            icon: "check",
            tone: "ok",
          },
          {
            key: "failed",
            label: t("admin:announce.failedCount"),
            value: format.number(total("failed")),
            icon: "alert",
            tone: total("failed") ? "bad" : "neutral",
          },
        ]}
      />
      <NewslettersPanel />
      <AdminGrid>
        <EmailSettings />
        <DigestDefault />
      </AdminGrid>
      <Deliveries status={status.data} />
    </AdminPage>
  );
}
