import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { FunctionalState } from "../../design-system/FunctionalState";
import { ApiError, DataRegion } from "../../state/regions";
import { FormMessage } from "./FormMessage";
import { authStrings as t, type VisibilityPreference } from "./strings";
import { ME_KEY, type Me } from "./useAuth";

type ExportOut = components["schemas"]["ExportOut"];

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "user.display_name_taken") return t.displayNameTaken;
    if (error.code === "user.avatar_invalid") return t.avatarInvalid;
    if (error.code === "admin.sole_admin_protected") return t.soleAdmin;
    if (error.status === 422 || error.status === 401) return error.message;
  }
  return t.genericError;
}

function ProfileSection({ me }: { me: Me }) {
  const ids = { name: useId(), bio: useId(), visibility: useId(), title: useId() };
  const queryClient = useQueryClient();
  const [displayName, setDisplayName] = useState(me.display_name ?? "");
  const [bio, setBio] = useState("");
  const [visibility, setVisibility] = useState<VisibilityPreference>("private");
  const mutation = useMutation({
    mutationFn: async () => {
      await api.PATCH("/api/v1/me/profile", {
        body: { display_name: displayName, fields: { bio: { value: bio || null, visibility } } },
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={submit} aria-labelledby={ids.title} className="auth-form">
      <h2 id={ids.title}>{t.profileTitle}</h2>
      {mutation.isError ? <FormMessage kind="error">{messageFor(mutation.error)}</FormMessage> : null}
      {mutation.isSuccess ? <FormMessage kind="success">{t.saved}</FormMessage> : null}
      <label htmlFor={ids.name}>{t.displayNameField}</label>
      <input
        id={ids.name}
        autoComplete="nickname"
        value={displayName}
        onChange={(event) => setDisplayName(event.target.value)}
      />
      <label htmlFor={ids.bio}>{t.bioField}</label>
      <textarea id={ids.bio} maxLength={1000} value={bio} onChange={(event) => setBio(event.target.value)} />
      <label htmlFor={ids.visibility}>{t.visibilityField}</label>
      <select
        id={ids.visibility}
        value={visibility}
        onChange={(event) => setVisibility(event.target.value as VisibilityPreference)}
      >
        {(Object.keys(t.visibility) as VisibilityPreference[]).map((key) => (
          <option key={key} value={key}>
            {t.visibility[key]}
          </option>
        ))}
      </select>
      <button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
        {t.save}
      </button>
    </form>
  );
}

function AvatarSection({ me }: { me: Me }) {
  const ids = { file: useId(), title: useId() };
  const queryClient = useQueryClient();
  const upload = useMutation({
    mutationFn: async (file: File) => {
      await api.PUT("/api/v1/me/avatar", {
        body: file as unknown as string,
        bodySerializer: (body) => body as unknown as BodyInit,
        headers: { "Content-Type": file.type || "application/octet-stream" },
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
  const remove = useMutation({
    mutationFn: async () => {
      await api.DELETE("/api/v1/me/avatar");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
  const error = upload.error ?? remove.error;

  return (
    <section aria-labelledby={ids.title} data-tour="avatar">
      <h2 id={ids.title}>{t.avatarTitle}</h2>
      {error ? <FormMessage kind="error">{messageFor(error)}</FormMessage> : null}
      {me.has_avatar ? (
        <img src={`/api/v1/users/${me.id}/avatar`} alt="" width={96} height={96} className="avatar" />
      ) : null}
      <label htmlFor={ids.file}>{t.avatarField}</label>
      <input
        id={ids.file}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) upload.mutate(file);
        }}
      />
      {me.has_avatar ? (
        <button type="button" onClick={() => remove.mutate()} disabled={remove.isPending}>
          {t.avatarRemove}
        </button>
      ) : null}
    </section>
  );
}

export function ExportSection() {
  const titleId = useId();
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
    <section aria-labelledby={titleId}>
      <h2 id={titleId}>{t.exportTitle}</h2>
      {request.isError ? <FormMessage kind="error">{messageFor(request.error)}</FormMessage> : null}
      <button type="button" onClick={() => request.mutate()} disabled={request.isPending}>
        {t.exportRequest}
      </button>
      {job ? (
        <p role="status">
          {t.exportStatus(job.status)}{" "}
          {job.status === "ready" ? (
            <a href={`/api/v1/me/export/${job.id}/content`} download>
              {t.exportDownload}
            </a>
          ) : (
            <button type="button" onClick={() => refresh.mutate(job.id)}>
              ↻<span className="sr-only">{t.exportStatus(job.status)}</span>
            </button>
          )}
        </p>
      ) : null}
    </section>
  );
}

export function DeletionSection() {
  const ids = { password: useId(), title: useId(), warning: useId() };
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: async () => (await api.POST("/api/v1/me/deletion", { body: { password } })).data,
    onSuccess: () => queryClient.setQueryData(ME_KEY, null),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <form onSubmit={submit} aria-labelledby={ids.title} aria-describedby={ids.warning} className="auth-form">
      <h2 id={ids.title}>{t.deletionTitle}</h2>
      <p id={ids.warning}>{t.deletionWarning}</p>
      {mutation.isError ? <FormMessage kind="error">{messageFor(mutation.error)}</FormMessage> : null}
      {mutation.data?.deletion_due_at ? (
        <FormMessage kind="success">
          {t.deletionRequested(new Date(mutation.data.deletion_due_at).toLocaleString())}
        </FormMessage>
      ) : null}
      <label htmlFor={ids.password}>{t.deletionConfirmPassword}</label>
      <input
        id={ids.password}
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" disabled={mutation.isPending || !password} aria-busy={mutation.isPending}>
        {t.deletionRequest}
      </button>
    </form>
  );
}

/** Account screen: profile, avatar, personal-data export and deletion (spec 002 US3/US5/US6). */
export function AccountPage() {
  return (
    <DataRegion<Me | null>
      label={t.accountTitle}
      queryKey={ME_KEY}
      queryFn={async () => (await api.GET("/api/v1/me")).data ?? null}
    >
      {(me) =>
        me ? (
          <div className="account-page">
            <h1>{t.accountTitle}</h1>
            <ProfileSection me={me} />
            <AvatarSection me={me} />
            <ExportSection />
            <DeletionSection />
          </div>
        ) : (
          <FunctionalState state="unauthorized" detail={t.accountTitle} />
        )
      }
    </DataRegion>
  );
}
