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
import { FormMessage } from "./FormMessage";
import { authStrings } from "./strings";
import { ME_KEY, type Me } from "./useAuth";
import "../community/profile/profile.css";

type ExportOut = components["schemas"]["ExportOut"];

function messageFor(error: unknown, t: ReturnType<typeof useT>): string {
  if (error instanceof ApiError) {
    if (error.code === "user.display_name_taken") return t("account:profile.nameTaken");
    if (error.code === "user.avatar_invalid") return t("account:photo.invalid");
    if (error.code === "admin.sole_admin_protected") return authStrings.soleAdmin;
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
      <MemberProfile memberId={me.id} heading={2} withBackground={false} />
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
    </SettingsPage>
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
