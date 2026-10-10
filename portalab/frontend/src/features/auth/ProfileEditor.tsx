import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, type FormEvent, useEffect, useId, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextAreaField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { SavedNote, SettingsCard } from "../account/SettingsKit";
import { FormMessage } from "./FormMessage";
import type { VisibilityPreference } from "./strings";
import { ME_KEY, type Me } from "./useAuth";

/**
 * Editing one's own profile (#46/#51): the picture (a button over the avatar of the profile's hero) and
 * the profile card (name, « About me » and who sees it) — shown on one's public profile and in My account.
 */
type ProfileOut = components["schemas"]["ProfileOut"];

const VISIBILITIES: readonly VisibilityPreference[] = ["public", "community", "leaderboard", "private"];

function messageFor(error: unknown, t: ReturnType<typeof useT>): string {
  if (error instanceof ApiError) {
    if (error.code === "user.display_name_taken") return t("account:profile.nameTaken");
    if (error.code === "user.avatar_invalid") return t("account:photo.invalid");
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
export function PhotoControl({ onChanged }: { onChanged: () => void }) {
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

export function ProfileCard({ me, onPhotoRemoved }: { me: Me; onPhotoRemoved: () => void }) {
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
        <div className="settings-fields">
          <TextField
            id={ids.name}
            label={t("account:profile.name")}
            autoComplete="nickname"
            maxLength={64}
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
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
        </div>
        <TextAreaField
          id={ids.bio}
          label={t("account:profile.bio")}
          hint={t("account:profile.bioHint")}
          maxLength={1000}
          rows={3}
          value={bio}
          onChange={(event) => setBio(event.target.value)}
        />
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
