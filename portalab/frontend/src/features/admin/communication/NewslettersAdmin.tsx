import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { AdminPage, AdminStats } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { AutomaticNewsletters } from "../../news/editions/AutomaticNewsletters";
import { EditionsAdmin } from "../../news/editions/EditionsAdmin";
import { Deliveries, type Status } from "./AnnouncementsAdmin";
import { DigestDefault } from "./EmailSettings";
import "../admin.css";

/**
 * ``/admin/newsletters`` (admin reorganisation, trial): everything that goes out by e-mail in one page — the
 * automatic newsletters, the default digest, how the e-mails are sent (with a test) and how they went.
 */
function EmailState({ enabled }: { enabled: boolean }) {
  const t = useT();
  return (
    <div className="email-state" data-on={enabled || undefined}>
      <Icon name="mail" size={18} />
      <span className="email-state__text">
        <strong>{t(enabled ? "admin:email.stateOn" : "admin:email.stateOff")}</strong>
        <small>{t("admin:email.stateHint")}</small>
      </span>
      <Link to="/admin/configuration?area=communication" className="ds-button ds-button--secondary">
        <Icon name="settings" size={16} />
        {t("admin:email.setUp")}
      </Link>
    </div>
  );
}

export default function NewslettersAdmin() {
  const t = useT();
  const format = useFormat();
  const status = useQuery({
    queryKey: ["admin", "notifications", "status"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/admin/notifications/status")).data as unknown as Status,
  });
  // issue 321: e-mails only — the portal's own notifications (the bell) are not e-mails
  const total = (s: string) =>
    (status.data?.deliveries ?? [])
      .filter((d) => d.channel === "email" && d.status === s)
      .reduce((a, d) => a + d.count, 0);
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
            label: t("admin:email.sentCount"),
            value: format.number(total("sent")),
            icon: "check",
            tone: "ok",
          },
          {
            key: "failed",
            label: t("admin:email.failedCount"),
            value: format.number(total("failed")),
            icon: "alert",
            tone: total("failed") ? "bad" : "neutral",
          },
        ]}
      />
      {/* issue 321: how the e-mails go out is set in Configuration — here, where it stands and the way there */}
      <EmailState enabled={Boolean(status.data?.email_enabled)} />
      {/* issue 325: the automatic newsletters write the self-writing editions — then their history, templates */}
      <AutomaticNewsletters />
      <EditionsAdmin />
      <DigestDefault />
      <Deliveries status={status.data} />
    </AdminPage>
  );
}
