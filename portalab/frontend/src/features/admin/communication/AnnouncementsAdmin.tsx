import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useSearchParams } from "react-router";
import { api } from "../../../api/client";
import {
  AdminGrid,
  AdminPage,
  AdminSection,
  AdminStats,
  AdminTabs,
  FormActions,
  FormGrid,
  StatusBadge,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { MaintenancePanel } from "./MaintenanceAdmin";
import "../admin.css";

/**
 * Announcements (027 hubs; notifications 010 admin API): send a message to every member — in their
 * notification centre and, for those who chose it, by e-mail — and set up the e-mail transport (with a test
 * sent to yourself). Delivery figures come from the notification status; titles and addresses are never
 * listed back.
 */
interface Status {
  email_enabled: boolean;
  deliveries: Array<{ channel: string; status: string; reason: string | null; count: number }>;
}

function Broadcast() {
  const t = useT();
  const client = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState("normal");
  const [kind, setKind] = useState("notification");
  const [link, setLink] = useState("");
  const send = useMutation({
    mutationFn: async () =>
      (
        await api.POST("/api/v1/admin/notifications/broadcast", {
          body: {
            title,
            body,
            priority: priority as "normal",
            kind: kind as "notification",
            dedup_key: `announcement:${Date.now()}`,
            action_url: link || null,
          },
        })
      ).data as { recipients: number },
    onSuccess: () => {
      setTitle("");
      setBody("");
      void client.invalidateQueries({ queryKey: ["admin", "notifications"] });
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    send.mutate();
  };
  return (
    <AdminSection
      title={t("admin:announce.new")}
      description={t("admin:announce.newHint")}
      icon="bell"
      span="full"
    >
      <form onSubmit={submit} className="admin-form">
        <FormGrid>
          <TextField
            label={t("admin:announce.title")}
            required
            minLength={3}
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <SelectField
            label={t("admin:announce.kind")}
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              if (e.target.value === "alert" && !["high", "critical"].includes(priority)) setPriority("high");
            }}
          >
            <option value="notification">{t("admin:announce.kinds.notification")}</option>
            <option value="alert">{t("admin:announce.kinds.alert")}</option>
          </SelectField>
          <SelectField
            label={t("admin:announce.priority")}
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
          >
            {["low", "normal", "high", "critical"].map((p) => (
              <option key={p} value={p} disabled={kind === "alert" && (p === "low" || p === "normal")}>
                {t(`admin:announce.priorities.${p}`)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("admin:announce.link")}
            hint={t("admin:announce.linkHint")}
            placeholder="/news"
            value={link}
            onChange={(e) => setLink(e.target.value)}
          />
          <div className="ds-field" data-span="full">
            <label htmlFor="announce-body">{t("admin:announce.body")}</label>
            <textarea
              id="announce-body"
              rows={5}
              maxLength={2000}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
        </FormGrid>
        {send.data ? (
          <p role="status" className="services-admin__ok">
            {t("admin:announce.sent", { count: send.data.recipients })}
          </p>
        ) : null}
        {send.isError ? (
          <p role="alert" className="services-admin__ko">
            {send.error instanceof ApiError ? send.error.message : t("admin:announce.failed")}
          </p>
        ) : null}
        <FormActions>
          <Button type="submit" disabled={send.isPending}>
            <Icon name="bell" size={16} />
            {t("admin:announce.send")}
          </Button>
        </FormActions>
      </form>
    </AdminSection>
  );
}

function Deliveries({ status }: { status: Status | undefined }) {
  const t = useT();
  const format = useFormat();
  const rows = status?.deliveries ?? [];
  return (
    <AdminSection title={t("admin:announce.deliveries")} icon="chart" flush>
      {rows.length === 0 ? (
        <p className="admin-muted admin-pad">{t("admin:announce.noDelivery")}</p>
      ) : (
        <ul className="admin-list">
          {rows.map((row) => (
            <li key={`${row.channel}-${row.status}-${row.reason ?? ""}`}>
              <span className="admin-list__main">
                <strong>{t(`admin:announce.channels.${row.channel}`)}</strong>
                {row.reason ? <span className="admin-muted">{row.reason}</span> : null}
              </span>
              <StatusBadge
                tone={
                  row.status === "failed"
                    ? "bad"
                    : row.status === "sent" || row.status === "delivered"
                      ? "ok"
                      : "neutral"
                }
              >
                {row.status}
              </StatusBadge>
              <strong>{format.number(row.count)}</strong>
            </li>
          ))}
        </ul>
      )}
    </AdminSection>
  );
}

const TABS = ["announce", "maintenance"] as const;

/**
 * Announcements (027 hubs, Communication): tell everyone now (and see deliveries) and plan maintenances.
 * Newsletters live in the news desk; the e-mail transport in System. Grouped on purpose:
 * everything that reaches members' inboxes lives here.
 */
export default function AnnouncementsAdmin() {
  const t = useT();
  const format = useFormat();
  const [params, setParams] = useSearchParams();
  const tab = (TABS as readonly string[]).includes(params.get("tab") ?? "")
    ? (params.get("tab") as string)
    : "announce";
  const status = useQuery({
    queryKey: ["admin", "notifications", "status"],
    retry: false,
    queryFn: async () => (await api.GET("/api/v1/admin/notifications/status")).data as unknown as Status,
  });
  const total = (s: string) =>
    (status.data?.deliveries ?? []).filter((d) => d.status === s).reduce((a, d) => a + d.count, 0);
  return (
    <AdminPage
      icon="bell"
      title={t("admin:announce.pageTitle")}
      description={t("admin:announce.subtitle")}
      tabs={
        <AdminTabs
          label={t("admin:announce.pageTitle")}
          current={tab}
          onChange={(next) => setParams(next === "announce" ? {} : { tab: next }, { replace: true })}
          tabs={TABS.map((key) => ({ key, label: t(`admin:announce.tabs.${key}`) }))}
        />
      }
    >
      {tab === "announce" ? (
        <>
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
          <AdminGrid>
            <Broadcast />
            <Deliveries status={status.data} />
          </AdminGrid>
        </>
      ) : null}
      {tab === "maintenance" ? <MaintenancePanel /> : null}
    </AdminPage>
  );
}
