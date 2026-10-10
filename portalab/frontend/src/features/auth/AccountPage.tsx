import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, type FormEvent, useEffect, useId, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextAreaField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { FunctionalState } from "../../design-system/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { ApiError, DataRegion } from "../../state/regions";
import { SavedNote, SettingsCard, SettingsGrid, SettingsPage } from "../account/SettingsKit";
import { useProfile } from "../community/api";
import type { Equipped } from "../community/profile/looks";
import { ProfileHero } from "../community/profile/ProfileHero";
import { FormMessage } from "./FormMessage";
import { authStrings, type VisibilityPreference } from "./strings";
import { ME_KEY, type Me } from "./useAuth";
import "../community/profile/profile.css";

type ExportOut = components["schemas"]["ExportOut"];
type ProfileOut = components["schemas"]["ProfileOut"];

const VISIBILITIES: readonly VisibilityPreference[] = ["public", "community", "leaderboard", "private"];

function messageFor(error: unknown, t: ReturnType<typeof useT>): string {
  if (error instanceof ApiError) {
    if (error.code === "user.display_name_taken") return t("account:profile.nameTaken");
    if (error.code === "user.avatar_invalid") return t("account:photo.invalid");
    if (error.code === "admin.sole_admin_protected") return authStrings.soleAdmin;
    if (error.status === 422 || error.status === 401) return error.message;
  }
  return t("account:error");
}

/** The member's own profile fields (to edit « About me » without losing what is there). */
function useOwnProfile(userId: string) {
  return useQuery({
    queryKey: ["identity", "profile", userId],
    retry: false,
    queryFn: async () =>
      (await api.GET("/api/v1/users/{user_id}/profile", { params: { path: { user_id: userId } } }))
        .data as ProfileOut,
  });
}

/** « Change the picture », over the avatar of the hero (and « remove » once there is one). */
function PhotoControl({ onChanged }: { onChanged: () => void }) {
  const t = useT();
  const fileId = useId();
  const queryClient = useQueryClient();
  const upload = useMutation({
    mutationFn: async (file: File) => {
      await api.PUT("/api/v1/me/avatar", {
        body: file as unknown as string,
        bodySerializer: (body) => body as unknown as BodyInit,
        headers: { "Content-Type": file.type || "application/octet-stream" },
      });
    },
    onSuccess: async () => {
      onChanged();
      await queryClient.invalidateQueries({ queryKey: ME_KEY });
    },
  });
  return (
    <>
      <label
        htmlFor={fileId}
        className="account-hero__photo"
        title={t("account:photo.change")}
        data-tour="avatar"
      >
        <Icon name={upload.isPending ? "spinner" : "image"} size={16} />
        <span className="visually-hidden">{t("account:photo.change")}</span>
      </label>
      <input
        id={fileId}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="visually-hidden"
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          const file = event.target.files?.[0];
          if (file) upload.mutate(file);
          event.target.value = "";
        }}
      />
      {upload.isError ? (
        <span className="visually-hidden" role="alert">
          {messageFor(upload.error, t)}
        </span>
      ) : null}
    </>
  );
}

function ProfileCard({ me, onPhotoRemoved }: { me: Me; onPhotoRemoved: () => void }) {
  const t = useT();
  const ids = { name: useId(), bio: useId() };
  const queryClient = useQueryClient();
  const own = useOwnProfile(me.id);
  const bioField = own.data?.fields?.find((field) => field.key === "bio");
  const [displayName, setDisplayName] = useState(me.display_name ?? "");
  const [bio, setBio] = useState("");
  const [visibility, setVisibility] = useState<VisibilityPreference>("private");
  // what is stored, once it arrives (« About me » and who sees it)
  useEffect(() => {
    if (!bioField) return;
    setBio(bioField.value ?? "");
    setVisibility(bioField.visibility);
  }, [bioField]);
  const save = useMutation({
    mutationFn: async () => {
      await api.PATCH("/api/v1/me/profile", {
        body: { display_name: displayName, fields: { bio: { value: bio || null, visibility } } },
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ME_KEY });
      await queryClient.invalidateQueries({ queryKey: ["identity", "profile", me.id] });
      await queryClient.invalidateQueries({ queryKey: ["community"] });
    },
  });
  const removePhoto = useMutation({
    mutationFn: async () => {
      await api.DELETE("/api/v1/me/avatar");
    },
    onSuccess: async () => {
      onPhotoRemoved();
      await queryClient.invalidateQueries({ queryKey: ME_KEY });
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  return (
    <SettingsCard
      id="account-profile"
      icon="user"
      title={t("account:profile.title")}
      hint={t("account:profile.hint")}
      aside={<SavedNote shown={save.isSuccess} text={t("account:saved")} />}
    >
      <form onSubmit={submit}>
        {save.isError ? <FormMessage kind="error">{messageFor(save.error, t)}</FormMessage> : null}
        <TextField
          id={ids.name}
          label={t("account:profile.name")}
          autoComplete="nickname"
          maxLength={64}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />
        <TextAreaField
          id={ids.bio}
          label={t("account:profile.bio")}
          hint={t("account:profile.bioHint")}
          maxLength={1000}
          rows={3}
          value={bio}
          onChange={(event) => setBio(event.target.value)}
        />
        <SelectField
          label={t("account:profile.visibility")}
          value={visibility}
          onChange={(event) => setVisibility(event.target.value as VisibilityPreference)}
        >
          {VISIBILITIES.map((key) => (
            <option key={key} value={key}>
              {t(`account:visibility.${key}`)}
            </option>
          ))}
        </SelectField>
        <div className="settings-actions">
          {me.has_avatar ? (
            <Button
              variant="ghost"
              className="ds-button--quiet-danger"
              disabled={removePhoto.isPending}
              onClick={() => removePhoto.mutate()}
            >
              <Icon name="trash" size={16} />
              {t("account:photo.remove")}
            </Button>
          ) : null}
          <Button type="submit" disabled={save.isPending} aria-busy={save.isPending}>
            <Icon name="check" size={16} />
            {t("account:save")}
          </Button>
        </div>
      </form>
    </SettingsCard>
  );
}

const LINKS = [
  { key: "profile", icon: "users", to: (id: string) => `/community/members/${id}` },
  { key: "progression", icon: "trophy", to: () => "/progression" },
  { key: "appearance", icon: "palette", to: () => "/settings/appearance" },
  { key: "privacy", icon: "shield", to: () => "/privacy" },
] as const;

function AccountView({ me }: { me: Me }) {
  const t = useT();
  const community = useProfile(me.id);
  const [version, setVersion] = useState(0);
  const name = me.display_name ?? me.login ?? "";
  const looks = (community.data?.looks ?? {}) as Equipped;
  const avatar = me.has_avatar ? `/api/v1/users/${me.id}/avatar${version ? `?v=${version}` : ""}` : null;
  return (
    <SettingsPage icon="user" title={t("account:title")} lead={t("account:lead")}>
      <div className="profile-page">
        <ProfileHero
          memberId={me.id}
          name={name}
          looks={looks}
          own
          heading={2}
          avatarSrc={avatar}
          avatarAction={<PhotoControl onChanged={() => setVersion(Date.now())} />}
        />
      </div>
      <SettingsGrid>
        <ProfileCard me={me} onPhotoRemoved={() => setVersion(Date.now())} />
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
      </SettingsGrid>
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
