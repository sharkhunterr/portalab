import { type FormEvent, useId, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { Dialog, DialogActions } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { Switch } from "../account/SettingsKit";
import {
  AGES,
  FEATURES,
  type HouseholdMember,
  type ProfileKind,
  type RestrictionSettings,
  useCreateProfile,
  useDeleteProfile,
  useSetPin,
  useUpdateProfile,
} from "./api";
import { ProfileFace } from "./ProfilePicker";

const KINDS: ProfileKind[] = ["standard", "child", "custom"];
const PRESETS: Record<ProfileKind, { restrictions: RestrictionSettings; community: boolean }> = {
  standard: { restrictions: { max_age: null, allow_unrated: true, blocked: [] }, community: true },
  child: {
    restrictions: { max_age: 12, allow_unrated: false, blocked: ["ai", "community", "requests", "shop"] },
    community: false,
  },
  custom: { restrictions: { max_age: null, allow_unrated: true, blocked: [] }, community: true },
};
const KIND_ICONS: Record<ProfileKind, string> = { standard: "user", child: "smile", custom: "sliders" };

/** Creating a profile, or (the master) setting one: its name, colour, kind, restrictions, PIN, community. */
export function ProfileEditor({
  member,
  position,
  palette,
  onClose,
}: {
  member: HouseholdMember | null;
  position: number;
  palette: readonly string[];
  onClose: () => void;
}) {
  const t = useT();
  const notify = useNotify();
  const formId = useId();
  const create = useCreateProfile();
  const update = useUpdateProfile();
  const remove = useDeleteProfile();
  const setPin = useSetPin();
  const editing = member !== null;
  const startKind = (member?.kind === "owner" ? "standard" : member?.kind) ?? "standard";
  const [name, setName] = useState(member?.display_name ?? "");
  const [kind, setKind] = useState<ProfileKind>(startKind);
  const [color, setColor] = useState(member?.color ?? palette[position % palette.length] ?? palette[0] ?? "");
  const [restrictions, setRestrictions] = useState<RestrictionSettings>(
    member?.restrictions ?? PRESETS[startKind].restrictions,
  );
  const [community, setCommunity] = useState(member?.community_visible ?? PRESETS[startKind].community);
  const [pin, setPinValue] = useState("");
  const [confirming, setConfirming] = useState(false);
  const pending = create.isPending || update.isPending || setPin.isPending || remove.isPending;
  const failed = [create.error, update.error, setPin.error, remove.error].find(Boolean);
  const pinInvalid = pin !== "" && !/^\d{4,6}$/.test(pin);

  const chooseKind = (next: ProfileKind) => {
    setKind(next);
    setRestrictions(PRESETS[next].restrictions);
    setCommunity(PRESETS[next].community);
  };
  const toggle = (feature: string, on: boolean) =>
    setRestrictions((r) => ({
      ...r,
      blocked: on ? [...(r.blocked ?? []), feature].sort() : (r.blocked ?? []).filter((f) => f !== feature),
    }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (pinInvalid || !name.trim()) return;
    try {
      if (editing) {
        await update.mutateAsync({
          id: member.id,
          display_name: name.trim(),
          color,
          kind,
          restrictions,
          community_visible: community,
        });
        if (pin) await setPin.mutateAsync({ id: member.id, pin });
        notify({ severity: "success", title: t("household:editor.saved") });
      } else {
        const created = await create.mutateAsync({
          display_name: name.trim(),
          kind,
          color,
          ...(pin ? { pin } : {}),
        });
        const preset = PRESETS[kind];
        if (
          JSON.stringify(preset.restrictions) !== JSON.stringify(restrictions) ||
          preset.community !== community
        )
          await update.mutateAsync({ id: created.id, restrictions, community_visible: community });
        notify({ severity: "success", title: t("household:editor.created") });
      }
      onClose();
    } catch {
      // the error is shown below
    }
  };

  const title = editing ? t("household:page.edit", { name: member.display_name }) : t("household:editor.new");
  return (
    <Dialog
      trigger={null}
      open
      size="lg"
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={title}
      closeLabel={t("household:editor.cancel")}
    >
      <form id={formId} className="household-editor" onSubmit={submit}>
        <div className="household-editor__identity">
          <ProfileFace
            member={{
              id: member?.id ?? "new",
              display_name: name || "?",
              color,
              has_avatar: Boolean(member?.has_avatar),
            }}
          />
          <div className="household-editor__fields">
            <TextField
              label={t("household:editor.name")}
              value={name}
              maxLength={64}
              required
              onChange={(event) => setName(event.target.value)}
            />
            <fieldset className="household-editor__colors">
              <legend>{t("household:editor.color")}</legend>
              {palette.map((swatch) => (
                <label key={swatch} style={{ "--swatch": swatch } as React.CSSProperties}>
                  <input
                    type="radio"
                    name={`${formId}-color`}
                    value={swatch}
                    checked={color === swatch}
                    onChange={() => setColor(swatch)}
                    aria-label={t("household:editor.colorOption", { color: swatch })}
                  />
                </label>
              ))}
            </fieldset>
          </div>
        </div>

        <fieldset className="household-editor__kinds">
          <legend>{t("household:editor.kind")}</legend>
          <p className="household-editor__hint">{t("household:editor.kindHint")}</p>
          {KINDS.map((option) => (
            <label key={option} data-checked={kind === option || undefined}>
              <input
                type="radio"
                name={`${formId}-kind`}
                value={option}
                checked={kind === option}
                onChange={() => chooseKind(option)}
              />
              <Icon name={KIND_ICONS[option]} size={20} />
              <span>{t(`household:kind.${option}`)}</span>
            </label>
          ))}
        </fieldset>

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.restrictions")}</legend>
          <SelectField
            label={t("household:editor.age")}
            value={restrictions.max_age ?? ""}
            onChange={(event) =>
              setRestrictions((r) => ({
                ...r,
                max_age: event.target.value === "" ? null : Number(event.target.value),
              }))
            }
          >
            <option value="">{t("household:editor.ageNone")}</option>
            {AGES.map((age) => (
              <option key={age} value={age}>
                {age === 0 ? t("household:editor.ageAll") : t("household:editor.ageN", { age })}
              </option>
            ))}
          </SelectField>
          <Switch
            label={t("household:editor.unrated")}
            checked={restrictions.allow_unrated ?? true}
            onChange={(event) => setRestrictions((r) => ({ ...r, allow_unrated: event.target.checked }))}
          />
          <p className="household-editor__hint">{t("household:editor.unratedHint")}</p>
          <fieldset className="household-editor__features">
            <legend className="household-editor__label">{t("household:editor.blocked")}</legend>
            {FEATURES.map((feature) => (
              <CheckboxField
                key={feature}
                label={t(`household:feature.${feature}`)}
                checked={(restrictions.blocked ?? []).includes(feature)}
                onChange={(event) => toggle(feature, event.target.checked)}
              />
            ))}
          </fieldset>
        </fieldset>

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.community")}</legend>
          <Switch
            label={t("household:editor.community")}
            checked={community}
            onChange={(event) => setCommunity(event.target.checked)}
          />
          <p className="household-editor__hint">{t("household:editor.communityHint")}</p>
        </fieldset>

        <fieldset className="household-editor__section">
          <legend>{t("household:editor.pin")}</legend>
          <TextField
            label={t("household:editor.pin")}
            hint={t("household:editor.pinHint")}
            type="password"
            inputMode="numeric"
            autoComplete="new-password"
            maxLength={6}
            value={pin}
            error={pinInvalid ? t("household:pin.hint") : undefined}
            onChange={(event) => setPinValue(event.target.value.replace(/\D/g, ""))}
          />
          {editing && member.has_pin ? (
            <Button
              variant="ghost"
              type="button"
              disabled={pending}
              onClick={() =>
                setPin.mutate(
                  { id: member.id, pin: null },
                  { onSuccess: () => notify({ severity: "success", title: t("household:myPin.saved") }) },
                )
              }
            >
              <Icon name="lock" size={16} />
              {t("household:editor.removePin")}
            </Button>
          ) : null}
        </fieldset>

        {editing ? (
          <div className="household-editor__danger">
            {confirming ? (
              <>
                <p role="alert">{t("household:editor.deleteConfirm", { name: member.display_name })}</p>
                <Button variant="ghost" type="button" onClick={() => setConfirming(false)}>
                  {t("household:editor.cancel")}
                </Button>
                <Button
                  variant="danger"
                  type="button"
                  disabled={pending}
                  onClick={() =>
                    remove.mutate(member.id, {
                      onSuccess: () => {
                        notify({ severity: "success", title: t("household:editor.deleted") });
                        onClose();
                      },
                    })
                  }
                >
                  <Icon name="trash" size={16} />
                  {t("household:editor.delete")}
                </Button>
              </>
            ) : (
              <Button variant="ghost" type="button" onClick={() => setConfirming(true)}>
                <Icon name="trash" size={16} />
                {t("household:editor.delete")}
              </Button>
            )}
          </div>
        ) : null}

        {failed ? (
          <p role="alert" className="household-error">
            {failed instanceof ApiError && failed.code === "household.limit"
              ? failed.message
              : t("household:error")}
          </p>
        ) : null}
        <DialogActions>
          <Button type="submit" disabled={pending || pinInvalid || !name.trim()}>
            <Icon name="check" size={16} />
            {editing ? t("household:editor.save") : t("household:editor.create")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
