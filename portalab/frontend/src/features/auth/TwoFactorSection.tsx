import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { SettingsCard } from "../account/SettingsKit";
import { FormMessage } from "./FormMessage";

type MfaStatus = components["schemas"]["MfaStatus"];
type MfaSetup = components["schemas"]["MfaSetup"];

const STATUS_KEY = ["identity", "me", "mfa"] as const;

function problem(error: unknown, t: ReturnType<typeof useT>): string {
  if (error instanceof ApiError) {
    if (error.code === "identity.password_current_wrong") return t("account:twoFactor.wrongPassword");
    if (error.code === "auth.mfa_code_wrong") return t("account:twoFactor.wrongCode");
    if (error.code === "auth.throttled")
      return t("account:signInPhrase.throttled", {
        minutes: Math.max(1, Math.ceil(Number(error.extensions.retry_after_seconds ?? 60) / 60)),
      });
  }
  return t("account:error");
}

/** Issue 408: the recovery codes, shown once — copy or save them before leaving. */
function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const text = `${codes.join("\n")}\n`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  const href = `data:text/plain;charset=utf-8,${encodeURIComponent(text)}`;
  return (
    <div className="two-factor__codes">
      <p className="settings-muted">
        <strong>{t("account:twoFactor.codesTitle")}</strong> — {t("account:twoFactor.codesHint")}
      </p>
      <ul aria-label={t("account:twoFactor.codesTitle")}>
        {codes.map((code) => (
          <li key={code}>
            <code>{code}</code>
          </li>
        ))}
      </ul>
      <div className="settings-actions">
        {copied ? (
          <span role="status" className="settings-saved">
            <Icon name="check" size={16} />
            {t("account:twoFactor.copied")}
          </span>
        ) : null}
        <Button variant="secondary" onClick={() => void copy()}>
          <Icon name="copy" size={16} />
          {t("account:twoFactor.copy")}
        </Button>
        <Button asChild variant="secondary">
          <a href={href} download="portalab-recovery-codes.txt">
            <Icon name="download" size={16} />
            {t("account:twoFactor.download")}
          </a>
        </Button>
        <Button onClick={onDone}>{t("account:twoFactor.codesDone")}</Button>
      </div>
    </div>
  );
}

/** Issue 408: the set-up — the password asked again, then the QR code, then a first code turns it on. */
function TurnOn({ onCodes }: { onCodes: (codes: string[]) => void }) {
  const t = useT();
  const client = useQueryClient();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const begin = useMutation({
    mutationFn: async () => (await api.POST("/api/v1/me/mfa/setup", { body: { password } })).data as MfaSetup,
    onSuccess: (data) => {
      setSetup(data);
      setPassword("");
    },
  });
  const confirm = useMutation({
    mutationFn: async () =>
      ((await api.POST("/api/v1/me/mfa/confirm", { body: { code: code.trim() } })).data?.codes ??
        []) as string[],
    onSuccess: (codes) => {
      setSetup(null);
      setCode("");
      onCodes(codes);
      void client.invalidateQueries({ queryKey: STATUS_KEY });
    },
  });

  if (!setup) {
    const submit = (event: FormEvent) => {
      event.preventDefault();
      begin.mutate();
    };
    return (
      <form onSubmit={submit}>
        {begin.isError ? <FormMessage kind="error">{problem(begin.error, t)}</FormMessage> : null}
        <TextField
          label={t("account:twoFactor.password")}
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <div className="settings-actions">
          <Button type="submit" disabled={begin.isPending || !password} aria-busy={begin.isPending}>
            <Icon name="shield" size={16} />
            {t("account:twoFactor.start")}
          </Button>
        </div>
      </form>
    );
  }
  const submit = (event: FormEvent) => {
    event.preventDefault();
    confirm.mutate();
  };
  return (
    <form onSubmit={submit} className="two-factor__setup">
      <p className="settings-muted">{t("account:twoFactor.scan")}</p>
      <img
        className="two-factor__qr"
        src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}`}
        alt={t("account:twoFactor.qrAlt")}
        width={200}
        height={200}
      />
      <details>
        <summary>{t("account:twoFactor.manual")}</summary>
        <code className="two-factor__secret">{setup.secret.replace(/(.{4})/g, "$1 ").trim()}</code>
      </details>
      {confirm.isError ? <FormMessage kind="error">{problem(confirm.error, t)}</FormMessage> : null}
      <TextField
        label={t("account:twoFactor.code")}
        autoComplete="one-time-code"
        inputMode="numeric"
        maxLength={8}
        required
        value={code}
        onChange={(event) => setCode(event.target.value)}
      />
      <div className="settings-actions">
        <Button variant="ghost" onClick={() => setSetup(null)}>
          {t("account:twoFactor.cancel")}
        </Button>
        <Button
          type="submit"
          disabled={confirm.isPending || code.trim().length < 6}
          aria-busy={confirm.isPending}
        >
          <Icon name="check" size={16} />
          {t("account:twoFactor.confirm")}
        </Button>
      </div>
    </form>
  );
}

/** Issue 408: on — the recovery codes left, new ones, or turning it off (password and a code). */
function TurnedOn({ left, onCodes }: { left: number; onCodes: (codes: string[]) => void }) {
  const t = useT();
  const client = useQueryClient();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const regenerate = useMutation({
    mutationFn: async () =>
      ((await api.POST("/api/v1/me/mfa/recovery-codes", { body: { password } })).data?.codes ??
        []) as string[],
    onSuccess: (codes) => {
      setPassword("");
      onCodes(codes);
      void client.invalidateQueries({ queryKey: STATUS_KEY });
    },
  });
  const off = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/me/mfa/off", { body: { password, code: code.trim() } });
    },
    onSuccess: () => {
      setPassword("");
      setCode("");
      void client.invalidateQueries({ queryKey: STATUS_KEY });
    },
  });
  const error = regenerate.error ?? off.error;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    off.mutate();
  };
  return (
    <form onSubmit={submit}>
      <p className="settings-muted">{t("account:twoFactor.left", { count: left })}</p>
      {error ? <FormMessage kind="error">{problem(error, t)}</FormMessage> : null}
      <div className="settings-fields">
        <TextField
          label={t("account:twoFactor.password")}
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <TextField
          label={t("account:twoFactor.offCode")}
          autoComplete="one-time-code"
          maxLength={32}
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
      </div>
      <div className="settings-actions">
        <Button
          variant="secondary"
          onClick={() => regenerate.mutate()}
          disabled={regenerate.isPending || !password}
          aria-busy={regenerate.isPending}
        >
          <Icon name="key" size={16} />
          {t("account:twoFactor.regenerate")}
        </Button>
        <Button
          type="submit"
          variant="danger"
          disabled={off.isPending || !password || code.trim().length < 6}
          aria-busy={off.isPending}
        >
          {t("account:twoFactor.off")}
        </Button>
      </div>
    </form>
  );
}

/** Issue 408: « Two-step verification » on the account page — local accounts only (the single sign-on
 * keeps its provider's own). */
export function TwoFactorSection({ hasPassword }: { hasPassword: boolean }) {
  const t = useT();
  const [codes, setCodes] = useState<string[] | null>(null);
  const status = useQuery({
    queryKey: STATUS_KEY,
    enabled: hasPassword,
    queryFn: async () => (await api.GET("/api/v1/me/mfa")).data as MfaStatus,
  });
  if (!hasPassword) {
    return (
      <SettingsCard icon="shield" title={t("account:twoFactor.title")} hint={t("account:twoFactor.notLocal")}>
        {null}
      </SettingsCard>
    );
  }
  const on = status.data?.enabled ?? false;
  return (
    <SettingsCard
      icon="shield"
      title={t("account:twoFactor.title")}
      hint={on ? t("account:twoFactor.hintOn") : t("account:twoFactor.hintOff")}
    >
      {codes ? (
        <RecoveryCodes codes={codes} onDone={() => setCodes(null)} />
      ) : !status.data ? null : on ? (
        <TurnedOn left={status.data.recovery_codes_left} onCodes={setCodes} />
      ) : (
        <TurnOn onCodes={setCodes} />
      )}
    </SettingsCard>
  );
}
