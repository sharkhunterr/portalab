import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import { AdminSection, FormActions, FormGrid } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import "../admin.css";

/**
 * E-mail (SMTP) transport (notifications 010; 027: in the System page) — sender, server, port, TLS and
 * account (the password is write-only), with a test e-mail sent to yourself.
 */
interface Setting {
  key: string;
  value: unknown;
}

const DIGEST_DEFAULT = "notifications.digest.defaultMode";
const EMAIL_KEYS = {
  enabled: "notifications.email.enabled",
  sender: "notifications.email.from",
  portal: "notifications.email.portalUrl",
  host: "notifications.email.smtp.host",
  port: "notifications.email.smtp.port",
  tls: "notifications.email.smtp.tls",
  username: "notifications.email.smtp.username",
} as const;

export function EmailSettings() {
  const t = useT();
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["admin", "notifications", "email"],
    retry: false,
    queryFn: async () => {
      const all = ((await api.GET("/api/v1/admin/config")).data as unknown as { settings: Setting[] })
        .settings;
      return Object.fromEntries(all.map((s) => [s.key, s.value]));
    },
  });
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [password, setPassword] = useState("");
  const value = (key: keyof typeof EMAIL_KEYS) => (draft ?? {})[key] ?? settings.data?.[EMAIL_KEYS[key]];
  const set = (key: keyof typeof EMAIL_KEYS, v: unknown) => setDraft({ ...(draft ?? {}), [key]: v });
  const save = useMutation({
    mutationFn: async () =>
      api.PUT("/api/v1/admin/notifications/email", {
        body: {
          enabled: Boolean(value("enabled")),
          sender: String(value("sender") ?? ""),
          portal_url: String(value("portal") ?? ""),
          host: String(value("host") ?? ""),
          port: Number(value("port") ?? 587),
          tls: Boolean(value("tls")),
          username: String(value("username") ?? ""),
          password: password || null,
        },
      }),
    onSuccess: () => {
      setPassword("");
      setDraft(null);
      void client.invalidateQueries({ queryKey: ["admin", "notifications"] });
    },
  });
  const test = useMutation({
    mutationFn: async () =>
      (await api.POST("/api/v1/admin/notifications/email/test")).data as { outcome: string },
  });
  return (
    <AdminSection
      title={t("admin:announce.email")}
      description={t("admin:announce.emailHint")}
      icon="message"
    >
      <form
        className="admin-form"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <CheckboxField
          label={t("admin:announce.emailEnabled")}
          checked={Boolean(value("enabled"))}
          onChange={(e) => set("enabled", e.target.checked)}
        />
        <FormGrid>
          <TextField
            label={t("admin:announce.sender")}
            value={String(value("sender") ?? "")}
            onChange={(e) => set("sender", e.target.value)}
          />
          <TextField
            label={t("admin:announce.portalUrl")}
            hint={t("admin:announce.portalUrlHint")}
            type="url"
            placeholder="https://portal.example.org"
            value={String(value("portal") ?? "")}
            onChange={(e) => set("portal", e.target.value)}
          />
          <TextField
            label={t("admin:announce.host")}
            value={String(value("host") ?? "")}
            onChange={(e) => set("host", e.target.value)}
          />
          <TextField
            label={t("admin:announce.port")}
            type="number"
            value={String(value("port") ?? 587)}
            onChange={(e) => set("port", Number(e.target.value))}
          />
          <TextField
            label={t("admin:announce.username")}
            value={String(value("username") ?? "")}
            onChange={(e) => set("username", e.target.value)}
          />
          <TextField
            label={t("admin:services.access.account")}
            hint={t("admin:services.writeOnly.hint")}
            type="password"
            autoComplete="off"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </FormGrid>
        <CheckboxField
          label={t("admin:announce.tls")}
          checked={Boolean(value("tls"))}
          onChange={(e) => set("tls", e.target.checked)}
        />
        {save.isSuccess ? (
          <p role="status" className="services-admin__ok">
            {t("admin:config.applied")}
          </p>
        ) : null}
        {save.isError ? (
          <p role="alert" className="services-admin__ko">
            {t("admin:announce.failed")}
          </p>
        ) : null}
        {test.data ? (
          <p
            role="status"
            className={test.data.outcome === "sent" ? "services-admin__ok" : "services-admin__ko"}
          >
            {test.data.outcome === "sent"
              ? t("admin:announce.testSent")
              : t("admin:announce.testFailed", { detail: test.data.outcome })}
          </p>
        ) : null}
        <FormActions>
          <Button type="button" variant="secondary" onClick={() => test.mutate()} disabled={test.isPending}>
            {t("admin:announce.test")}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {t("admin:announce.saveEmail")}
          </Button>
        </FormActions>
      </form>
    </AdminSection>
  );
}

export function DigestDefault() {
  const t = useT();
  const client = useQueryClient();
  const current = useQuery({
    queryKey: ["admin", "notifications", "digest"],
    retry: false,
    queryFn: async () => {
      const all = ((await api.GET("/api/v1/admin/config")).data as unknown as { settings: Setting[] })
        .settings;
      return String(all.find((s) => s.key === DIGEST_DEFAULT)?.value ?? "off");
    },
  });
  const save = useMutation({
    mutationFn: async (mode: string) =>
      api.PUT("/api/v1/admin/config", {
        body: {
          changes: [{ key: DIGEST_DEFAULT, value: mode, scope: "global", scope_ref: "", unset: false }],
          reason: "newsletter",
        },
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["admin", "notifications", "digest"] }),
  });
  return (
    <AdminSection
      title={t("admin:announce.newsletter")}
      description={t("admin:announce.newsletterHint")}
      icon="newspaper"
    >
      <fieldset className="ds-subnav" aria-label={t("admin:announce.newsletter")}>
        {(["off", "daily", "weekly"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            aria-pressed={current.data === mode}
            onClick={() => save.mutate(mode)}
          >
            {t(`admin:announce.digest.${mode}`)}
          </button>
        ))}
      </fieldset>
      <p className="admin-muted">{t("admin:announce.newsletterNote")}</p>
      {save.isSuccess ? (
        <p role="status" className="services-admin__ok">
          {t("admin:config.applied")}
        </p>
      ) : null}
    </AdminSection>
  );
}
