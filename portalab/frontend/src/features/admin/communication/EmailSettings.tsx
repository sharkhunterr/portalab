import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import { AdminSection, FormActions, FormGrid, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import "../admin.css";

interface Setting {
  key: string;
  value: unknown;
  source?: string;
}

export const EMAIL_KEYS = {
  enabled: "notifications.email.enabled",
  sender: "notifications.email.from",
  portal: "notifications.email.portalUrl",
  host: "notifications.email.smtp.host",
  port: "notifications.email.smtp.port",
  tls: "notifications.email.smtp.tls",
  username: "notifications.email.smtp.username",
} as const;
export const SMTP_PASSWORD = "notifications.email.smtp.password";

type Security = "none" | "starttls" | "ssl";
/** The usual providers: their server, port and security (issue 319). */
const PRESETS: Record<string, { host: string; port: number; security: Security }> = {
  gmail: { host: "smtp.gmail.com", port: 587, security: "starttls" },
  outlook: { host: "smtp.office365.com", port: 587, security: "starttls" },
  ovh: { host: "ssl0.ovh.net", port: 465, security: "ssl" },
  brevo: { host: "smtp-relay.brevo.com", port: 587, security: "starttls" },
  local: { host: "localhost", port: 25, security: "none" },
};
const PORTS: Record<Security, number> = { none: 25, starttls: 587, ssl: 465 };

/** The server's own rule: TLS on port 465 is SSL/TLS from the start, elsewhere STARTTLS. */
function securityOf(tls: boolean, port: number): Security {
  return !tls ? "none" : port === 465 ? "ssl" : "starttls";
}

function presetOf(host: string): string {
  return Object.entries(PRESETS).find(([, preset]) => preset.host === host)?.[0] ?? "custom";
}

/**
 * E-mail sending (notifications 010; issue 319 redesign): one form, in the order it is set up — sending on or
 * off, the server (a provider's preset, or its address, port and security), the account (its password
 * write-only), the sender, the portal's address for the links and pictures — saved together, then tested
 * with what was just saved.
 */
export function EmailSettings() {
  const t = useT();
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["admin", "notifications", "email"],
    retry: false,
    queryFn: async () => {
      const all = ((await api.GET("/api/v1/admin/config")).data as unknown as { settings: Setting[] })
        .settings;
      return Object.fromEntries(all.map((s) => [s.key, s]));
    },
  });
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [password, setPassword] = useState("");
  const value = (key: keyof typeof EMAIL_KEYS) =>
    key in draft ? draft[key] : settings.data?.[EMAIL_KEYS[key]]?.value;
  const set = (patch: Partial<Record<keyof typeof EMAIL_KEYS, unknown>>) => setDraft({ ...draft, ...patch });
  const enabled = Boolean(value("enabled"));
  const host = String(value("host") ?? "");
  const port = Number(value("port") ?? 587);
  const security = securityOf(Boolean(value("tls")), port);
  const preset = presetOf(host);
  const hasPassword = (settings.data?.[SMTP_PASSWORD]?.source ?? "default") !== "default";
  // issue 319: a refused test says why (an account without an address above all), never silently
  const test = useMutation({
    mutationFn: async () => {
      const refused = (error: unknown) => ({
        outcome: `refused:${(error as { code?: string } | null)?.code ?? "unknown"}`,
      });
      try {
        const { data, error } = await api.POST("/api/v1/admin/notifications/email/test");
        return error ? refused(error) : (data as { outcome: string });
      } catch (error) {
        return refused(error); // the client throws the API's refusals
      }
    },
  });
  const save = useMutation({
    mutationFn: async (andTest: boolean) => {
      const { error } = await api.PUT("/api/v1/admin/notifications/email", {
        body: {
          enabled,
          sender: String(value("sender") ?? ""),
          portal_url: String(value("portal") ?? ""),
          host,
          port,
          tls: security !== "none",
          username: String(value("username") ?? ""),
          password: password || null,
        },
      });
      if (error) throw error;
      return andTest;
    },
    onSuccess: (andTest) => {
      setPassword("");
      setDraft({});
      void client.invalidateQueries({ queryKey: ["admin", "notifications"] });
      void client.invalidateQueries({ queryKey: ["admin", "config"] });
      if (andTest) test.mutate();
    },
  });
  return (
    <AdminSection
      title={t("admin:email.title")}
      description={t("admin:email.intro")}
      icon="mail"
      actions={
        <StatusBadge tone={enabled ? "ok" : "neutral"}>
          {enabled ? t("admin:email.on") : t("admin:email.off")}
        </StatusBadge>
      }
      span="full"
    >
      <form
        className="admin-form email-setup"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(false);
        }}
      >
        <div className="email-setup__switch" data-on={enabled || undefined}>
          <CheckboxField
            label={t("admin:email.enabled")}
            checked={enabled}
            onChange={(e) => set({ enabled: e.target.checked })}
          />
          <p className="admin-muted">{t(enabled ? "admin:email.enabledHint" : "admin:email.offHint")}</p>
        </div>

        <fieldset className="email-setup__block">
          <legend>
            <span className="email-setup__step">1</span>
            {t("admin:email.server")}
          </legend>
          <FormGrid>
            <SelectField
              label={t("admin:email.provider")}
              value={preset}
              onChange={(e) => {
                const chosen = PRESETS[e.target.value];
                if (chosen) set({ host: chosen.host, port: chosen.port, tls: chosen.security !== "none" });
              }}
            >
              <option value="custom">{t("admin:email.preset.custom")}</option>
              {Object.keys(PRESETS).map((key) => (
                <option key={key} value={key}>
                  {t(`admin:email.preset.${key}`)}
                </option>
              ))}
            </SelectField>
            <TextField
              label={t("admin:email.host")}
              placeholder="smtp.example.org"
              required={enabled}
              value={host}
              onChange={(e) => set({ host: e.target.value.trim() })}
            />
            <SelectField
              label={t("admin:email.security")}
              value={security}
              onChange={(e) => {
                const next = e.target.value as Security;
                // a usual port follows the security chosen; a port of one's own stays
                const usual = Object.values(PORTS).includes(port);
                set({ tls: next !== "none", ...(usual ? { port: PORTS[next] } : {}) });
              }}
            >
              {(["starttls", "ssl", "none"] as const).map((option) => (
                <option key={option} value={option}>
                  {t(`admin:email.securityChoice.${option}`)}
                </option>
              ))}
            </SelectField>
            <TextField
              label={t("admin:email.port")}
              type="number"
              min={1}
              max={65535}
              value={String(port)}
              onChange={(e) => set({ port: Number(e.target.value) })}
            />
          </FormGrid>
          {preset !== "custom" ? (
            <p className="admin-muted email-setup__tip">{t(`admin:email.presetTip.${preset}`)}</p>
          ) : null}
        </fieldset>

        <fieldset className="email-setup__block">
          <legend>
            <span className="email-setup__step">2</span>
            {t("admin:email.account")}
          </legend>
          <FormGrid>
            <TextField
              label={t("admin:email.username")}
              hint={t("admin:email.usernameHint")}
              autoComplete="off"
              value={String(value("username") ?? "")}
              onChange={(e) => set({ username: e.target.value.trim() })}
            />
            <TextField
              label={t("admin:email.password")}
              hint={hasPassword ? t("admin:email.passwordKept") : t("admin:email.passwordHint")}
              placeholder={hasPassword ? "••••••••" : ""}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </FormGrid>
        </fieldset>

        <fieldset className="email-setup__block">
          <legend>
            <span className="email-setup__step">3</span>
            {t("admin:email.from")}
          </legend>
          <FormGrid>
            <TextField
              label={t("admin:email.sender")}
              hint={t("admin:email.senderHint")}
              type="email"
              placeholder="portail@example.org"
              required={enabled}
              value={String(value("sender") ?? "")}
              onChange={(e) => set({ sender: e.target.value.trim() })}
            />
            <TextField
              label={t("admin:email.portalUrl")}
              hint={t("admin:email.portalUrlHint")}
              type="url"
              placeholder="https://portail.example.org"
              value={String(value("portal") ?? "")}
              onChange={(e) => set({ portal: e.target.value.trim() })}
            />
          </FormGrid>
        </fieldset>

        {save.isError ? (
          <p role="alert" className="services-admin__ko">
            {t("admin:email.saveFailed")}
          </p>
        ) : save.isSuccess && !test.isPending && !test.data ? (
          <p role="status" className="services-admin__ok">
            {t("admin:email.saved")}
          </p>
        ) : null}
        {test.data ? (
          <p
            role="status"
            className={test.data.outcome === "sent" ? "services-admin__ok" : "services-admin__ko"}
          >
            {test.data.outcome === "sent"
              ? t("admin:email.testSent")
              : test.data.outcome === "refused:notifications.no_address"
                ? t("admin:email.noAddress")
                : t("admin:email.testFailed", {
                    detail: test.data.outcome.replace(/^(failed|refused):/, ""),
                  })}
          </p>
        ) : null}
        <FormActions>
          <Button
            type="button"
            variant="secondary"
            disabled={save.isPending || test.isPending || !enabled}
            onClick={() => save.mutate(true)}
          >
            <Icon name="send" size={16} />
            {t("admin:email.saveAndTest")}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            <Icon name="check" size={16} />
            {t("admin:email.save")}
          </Button>
        </FormActions>
      </form>
    </AdminSection>
  );
}
