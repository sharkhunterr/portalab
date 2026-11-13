import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { FunctionalState } from "../../design-system/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { ApiError, DataRegion } from "../../state/regions";
import { SettingsCard, SettingsPage } from "../account/SettingsKit";
import { MemberProfile } from "../community/profile/ProfilePage";
import { CommunityPresence } from "./CommunityPresence";
import { FormMessage } from "./FormMessage";
import { ME_KEY, type Me } from "./useAuth";
import "../community/profile/profile.css";
import { passwordRuleMessage } from "./passwordRules";

type ExportOut = components["schemas"]["ExportOut"];

function messageFor(error: unknown, t: ReturnType<typeof useT>): string {
  if (error instanceof ApiError) {
    if (error.code === "user.display_name_taken") return t("account:profile.nameTaken");
    if (error.code === "user.avatar_invalid") return t("account:photo.invalid");
    if (error.code === "admin.sole_admin_protected") return t("account:auth.soleAdmin");
    if (error.status === 422 || error.status === 401) return error.message;
  }
  return t("account:error");
}

const LINKS = [
  { key: "profile", icon: "users", to: (id: string) => `/community/members/${id}` },
  { key: "progression", icon: "trophy", to: () => "/progression" },
  { key: "appearance", icon: "palette", to: () => "/settings/appearance" },
  { key: "privacy", icon: "shield", to: () => "/privacy" },
] as const;

function AccountView({ me }: { me: Me }) {
  const t = useT();
  return (
    <SettingsPage icon="user" title={t("account:title")} lead={t("account:lead")}>
      <MemberProfile memberId={me.id} heading={2} />
      <CommunityPresence />
      <SettingsCard icon="compass" title={t("account:links.title")} hint={t("account:links.hint")}>
        <ul className="account-links">
          {LINKS.map((link) => (
            <li key={link.key}>
              <Link to={link.to(me.id)}>
                <Icon name={link.icon} size={18} />
                {t(`account:links.${link.key}`)}
              </Link>
            </li>
          ))}
        </ul>
      </SettingsCard>
      <PasswordSection hasPassword={me.has_password ?? true} />
    </SettingsPage>
  );
}

function passwordMessage(error: unknown, t: ReturnType<typeof useT>): string {
  if (error instanceof ApiError) {
    if (error.code === "identity.password_current_wrong") return t("account:signInPhrase.wrong");
    if (error.code === "identity.password_unchanged") return t("account:signInPhrase.unchanged");
    if (error.code === "identity.password_not_local") return t("account:signInPhrase.notLocal");
    const rule = passwordRuleMessage(error, t);
    if (rule) return rule;
    if (error.code === "auth.throttled")
      return t("account:signInPhrase.throttled", {
        minutes: Math.max(1, Math.ceil(Number(error.extensions.retry_after_seconds ?? 60) / 60)),
      });
  }
  return t("account:error");
}

/** « Change my password »: the current one, then the new one twice; the other devices are signed out. */
function PasswordSection({ hasPassword }: { hasPassword: boolean }) {
  const t = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const mismatch = again !== "" && again !== next;
  const mutation = useMutation({
    mutationFn: async () =>
      (
        await api.POST("/api/v1/me/password", {
          body: { current_password: current, new_password: next },
        })
      ).data,
    onSuccess: () => {
      setCurrent("");
      setNext("");
      setAgain("");
    },
  });
  if (!hasPassword) {
    return (
      <SettingsCard
        icon="key"
        title={t("account:signInPhrase.title")}
        hint={t("account:signInPhrase.notLocal")}
      >
        {null}
      </SettingsCard>
    );
  }
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!mismatch) mutation.mutate();
  };
  return (
    <SettingsCard icon="key" title={t("account:signInPhrase.title")} hint={t("account:signInPhrase.hint")}>
      <form onSubmit={submit} className="account-password">
        {mutation.isError ? (
          <FormMessage kind="error">{passwordMessage(mutation.error, t)}</FormMessage>
        ) : null}
        {mutation.isSuccess ? (
          <FormMessage kind="success">
            {t("account:signInPhrase.changed", { count: mutation.data?.other_sessions_signed_out ?? 0 })}
          </FormMessage>
        ) : null}
        <TextField
          label={t("account:signInPhrase.current")}
          type="password"
          autoComplete="current-password"
          required
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
        />
        <TextField
          label={t("account:signInPhrase.new")}
          type="password"
          autoComplete="new-password"
          required
          value={next}
          onChange={(event) => setNext(event.target.value)}
        />
        <TextField
          label={t("account:signInPhrase.again")}
          type="password"
          autoComplete="new-password"
          required
          value={again}
          error={mismatch ? t("account:signInPhrase.mismatch") : undefined}
          onChange={(event) => setAgain(event.target.value)}
        />
        <div className="settings-actions">
          <Button
            type="submit"
            disabled={mutation.isPending || !current || !next || !again || mismatch}
            aria-busy={mutation.isPending}
          >
            <Icon name="key" size={16} />
            {t("account:signInPhrase.submit")}
          </Button>
        </div>
      </form>
    </SettingsCard>
  );
}

/** « Request a copy of my data » (shown in the privacy centre). */
export function ExportSection() {
  const t = useT();
  const [job, setJob] = useState<ExportOut | null>(null);
  const request = useMutation({
    mutationFn: async () => (await api.POST("/api/v1/me/export")).data as ExportOut,
    onSuccess: setJob,
  });
  const refresh = useMutation({
    mutationFn: async (id: string) =>
      (await api.GET("/api/v1/me/export/{export_id}", { params: { path: { export_id: id } } }))
        .data as ExportOut,
    onSuccess: setJob,
  });
  return (
    <SettingsCard icon="package" title={t("account:export.title")} hint={t("account:export.hint")}>
      {request.isError ? <FormMessage kind="error">{messageFor(request.error, t)}</FormMessage> : null}
      {job ? (
        <p role="status" className="settings-preview">
          <Icon name={job.status === "ready" ? "check" : "hourglass"} size={18} />
          {t("account:export.status", { status: job.status })}
          {job.status === "ready" ? (
            <a href={`/api/v1/me/export/${job.id}/content`} download>
              {t("account:export.download")}
            </a>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => refresh.mutate(job.id)}
              aria-label={t("account:export.refresh")}
            >
              <Icon name="sync" size={16} />
            </Button>
          )}
        </p>
      ) : null}
      <div className="settings-actions">
        <Button variant="secondary" onClick={() => request.mutate()} disabled={request.isPending}>
          <Icon name="package" size={16} />
          {t("account:export.request")}
        </Button>
      </div>
    </SettingsCard>
  );
}

/** « Delete my account » (shown in the privacy centre). */
export function DeletionSection() {
  const t = useT();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: async () => (await api.POST("/api/v1/me/deletion", { body: { password } })).data,
    onSuccess: () => queryClient.setQueryData(ME_KEY, null),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };
  return (
    <SettingsCard
      icon="trash"
      tone="danger"
      title={t("account:deletion.title")}
      hint={t("account:deletion.hint")}
    >
      <form onSubmit={submit}>
        {mutation.isError ? <FormMessage kind="error">{messageFor(mutation.error, t)}</FormMessage> : null}
        {mutation.data?.deletion_due_at ? (
          <FormMessage kind="success">
            {t("account:deletion.requested", {
              until: new Date(mutation.data.deletion_due_at).toLocaleString(),
            })}
          </FormMessage>
        ) : null}
        <TextField
          label={t("account:deletion.confirm")}
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <div className="settings-actions">
          <Button
            type="submit"
            variant="danger"
            disabled={mutation.isPending || !password}
            aria-busy={mutation.isPending}
          >
            <Icon name="trash" size={16} />
            {t("account:deletion.request")}
          </Button>
        </div>
      </form>
    </SettingsCard>
  );
}

/** Account screen (spec 002 US3; #46): the profile's hero, then the profile card and shortcuts. */
export function AccountPage() {
  const t = useT();
  return (
    <DataRegion<Me | null>
      label={t("account:region")}
      queryKey={ME_KEY}
      queryFn={async () => (await api.GET("/api/v1/me")).data ?? null}
    >
      {(me) =>
        me ? <AccountView me={me} /> : <FunctionalState state="unauthorized" detail={t("account:title")} />
      }
    </DataRegion>
  );
}
