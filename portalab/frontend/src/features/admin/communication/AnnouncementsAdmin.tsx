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
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { StatusBanner } from "../../../shell/status/StatusBanner";
import { ApiError } from "../../../state/regions";
import { MaintenancePanel } from "./MaintenanceAdmin";
import "../admin.css";

/**
 * Announcements (027 hubs; notifications 010 admin API): send a message to every member — in their
 * notification centre and, for those who chose it, by e-mail — and set up the e-mail transport (with a test
 * sent to yourself). Delivery figures come from the notification status; titles and addresses are never
 * listed back.
 */
/**
 * 027: what kind of announcement — one choice, in its colour, that sets how it reaches members: the tone of
 * its banner and notification, whether it is an alert, its priority (an urgent one reaches even those who
 * muted announcements, is never held for a digest, and its banner cannot be closed).
 */
const TYPES = {
  info: { icon: "megaphone", kind: "notification", priority: "normal" },
  success: { icon: "sparkles", kind: "notification", priority: "normal" },
  warning: { icon: "alert", kind: "alert", priority: "high" },
  critical: { icon: "alert", kind: "alert", priority: "critical" },
} as const;
type AnnouncementType = keyof typeof TYPES;

interface Status {
  email_enabled: boolean;
  deliveries: Array<{ channel: string; status: string; reason: string | null; count: number }>;
}

function Broadcast() {
  const t = useT();
  const client = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [type, setType] = useState<AnnouncementType>("info");
  const [link, setLink] = useState("");
  // 027: where it goes — any of a notification, an e-mail, a banner (until a date)
  const [channels, setChannels] = useState<string[]>(["notification"]);
  const [until, setUntil] = useState(() => {
    const date = new Date(Date.now() + 7 * 86_400_000);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  });
  const toggle = (channel: string, on: boolean) =>
    setChannels(on ? [...new Set([...channels, channel])] : channels.filter((c) => c !== channel));
  const send = useMutation({
    mutationFn: async () =>
      (
        await api.POST("/api/v1/admin/notifications/broadcast", {
          body: {
            title,
            body,
            priority: TYPES[type].priority,
            kind: TYPES[type].kind,
            dedup_key: `announcement:${Date.now()}`,
            action_url: link || null,
            channels: channels as Array<"notification" | "email" | "banner">,
            tone: type,
            banner_until: channels.includes("banner") && until ? new Date(until).toISOString() : null,
          },
        })
      ).data as { recipients: number },
    onSuccess: () => {
      setTitle("");
      setBody("");
      void client.invalidateQueries({ queryKey: ["admin", "notifications"] });
      void client.invalidateQueries({ queryKey: ["announcements"] });
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
        <fieldset className="announce-types">
          <legend>{t("admin:announce.type")}</legend>
          {(Object.keys(TYPES) as AnnouncementType[]).map((value) => (
            <label key={value} className="announce-type" data-tone={value}>
              <input
                type="radio"
                name="announce-type"
                value={value}
                checked={type === value}
                onChange={() => setType(value)}
              />
              <span className="announce-type__icon" aria-hidden="true">
                <Icon name={TYPES[value].icon} size={16} />
              </span>
              <span className="announce-type__text">
                <strong>{t(`admin:announce.types.${value}`)}</strong>
                <small>{t(`admin:announce.types.${value}Hint`)}</small>
              </span>
            </label>
          ))}
        </fieldset>
        <FormGrid>
          <TextField
            label={t("admin:announce.title")}
            required
            minLength={3}
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
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
        <fieldset className="announce-channels">
          <legend>{t("admin:announce.channels.title")}</legend>
          {(["notification", "email", "banner"] as const).map((channel) => (
            <CheckboxField
              key={channel}
              label={t(`admin:announce.channels.${channel}`)}
              hint={t(`admin:announce.channels.${channel}Hint`)}
              checked={channels.includes(channel)}
              onChange={(e) => toggle(channel, e.target.checked)}
            />
          ))}
          {channels.includes("banner") ? (
            <TextField
              label={t("admin:announce.bannerUntil")}
              type="datetime-local"
              value={until}
              onChange={(e) => setUntil(e.target.value)}
            />
          ) : null}
          {/* what the banner will look like, in the chosen type's colour */}
          {channels.includes("banner") ? (
            <div className="announce-preview">
              <span className="announce-preview__label">{t("admin:announce.preview")}</span>
              <StatusBanner
                tone={type}
                icon={TYPES[type].icon}
                eyebrow={[t("notifications:banner.announcement")]}
                title={title || t("admin:announce.previewTitle")}
                text={body ? body.split("\n")[0] : null}
                details={link || null}
                detailsLabel={t("notifications:banner.more")}
                onClose={type === "critical" ? undefined : () => undefined}
              />
            </div>
          ) : null}
        </fieldset>
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
          <Button type="submit" disabled={send.isPending || !channels.length}>
            <Icon name="bell" size={16} />
            {t("admin:announce.send")}
          </Button>
        </FormActions>
      </form>
    </AdminSection>
  );
}

interface AnnouncementRow {
  id: string;
  title: string;
  tone: string;
  channels: string[];
  banner: boolean;
  banner_until: string | null;
  recipients: number;
  created_at: string;
  ended_at: string | null;
}

/** 027: the latest announcements — through which channels, whether the banner still shows (and end it). */
function History() {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const rows = useQuery({
    queryKey: ["admin", "notifications", "announcements"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/announcements")).data ?? []) as unknown as AnnouncementRow[],
  });
  const end = useMutation({
    mutationFn: async (id: string) =>
      api.POST("/api/v1/admin/announcements/{announcement_id}/end", {
        params: { path: { announcement_id: id } },
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["admin", "notifications", "announcements"] });
      void client.invalidateQueries({ queryKey: ["announcements"] });
    },
  });
  const now = Date.now();
  return (
    <AdminSection title={t("admin:announce.history")} icon="megaphone" span="full" flush>
      {rows.data && !rows.data.length ? (
        <p className="admin-muted admin-pad">{t("admin:announce.noHistory")}</p>
      ) : null}
      <ul className="admin-list">
        {(rows.data ?? []).map((row) => {
          const live =
            row.banner && !row.ended_at && (!row.banner_until || Date.parse(row.banner_until) > now);
          return (
            <li key={row.id}>
              <span className="admin-list__main">
                <strong>{row.title}</strong>
                <span className="admin-muted">
                  {format.dateTime(row.created_at)} ·{" "}
                  {row.channels.map((c) => t(`admin:announce.channels.${c}`)).join(" · ")}
                  {row.recipients ? ` · ${t("admin:announce.sent", { count: row.recipients })}` : ""}
                </span>
              </span>
              {live ? (
                <>
                  <StatusBadge tone="ok">
                    {row.banner_until
                      ? t("admin:announce.bannerLiveUntil", { date: format.dateTime(row.banner_until) })
                      : t("admin:announce.bannerLive")}
                  </StatusBadge>
                  <Button variant="secondary" disabled={end.isPending} onClick={() => end.mutate(row.id)}>
                    {t("admin:announce.endBanner")}
                  </Button>
                </>
              ) : null}
            </li>
          );
        })}
      </ul>
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
          <History />
        </>
      ) : null}
      {tab === "maintenance" ? <MaintenancePanel /> : null}
    </AdminPage>
  );
}
