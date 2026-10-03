import { type FormEvent, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { type CommunityEvent, type CommunityEventInput, useEventAdmin } from "../api";

function localInput(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

/** Event editor (spec 012 T014): moderators/Admin create and edit community events; the server decides. */
export function EventEditor({ event, onDone }: { event: CommunityEvent | null; onDone: () => void }) {
  const t = useT();
  const { save } = useEventAdmin();
  const [title, setTitle] = useState(event?.title ?? "");
  const [description, setDescription] = useState(event?.description_md ?? "");
  const [startsAt, setStartsAt] = useState(localInput(event?.starts_at));
  const [endsAt, setEndsAt] = useState(localInput(event?.ends_at));
  const [allDay, setAllDay] = useState(event?.all_day ?? false);
  const [zone, setZone] = useState(event?.reference_tz ?? Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [audience, setAudience] = useState<CommunityEventInput["audience"]>(
    (event?.audience as CommunityEventInput["audience"] | undefined) ?? "community",
  );
  const [roles, setRoles] = useState((event?.audience_roles ?? []).join(", "));

  const submit = (form: FormEvent) => {
    form.preventDefault();
    const body: CommunityEventInput = {
      title,
      description_md: description,
      starts_at: new Date(startsAt).toISOString(),
      ends_at: endsAt ? new Date(endsAt).toISOString() : null,
      all_day: allDay,
      reference_tz: zone,
      audience,
      audience_roles:
        audience === "roles"
          ? roles
              .split(",")
              .map((r) => r.trim())
              .filter(Boolean)
          : [],
    };
    save.mutate({ id: event?.id ?? null, body }, { onSuccess: onDone });
  };

  return (
    <form className="ds-card ds-stack" onSubmit={submit}>
      <TextField
        label={t("community:events.form.title")}
        value={title}
        required
        maxLength={200}
        onChange={(e) => setTitle(e.target.value)}
      />
      <div className="ds-field">
        <label htmlFor="community-event-description">{t("community:events.form.description")}</label>
        <textarea
          id="community-event-description"
          rows={5}
          maxLength={20000}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <TextField
        type="datetime-local"
        label={t("community:events.form.startsAt")}
        value={startsAt}
        required
        onChange={(e) => setStartsAt(e.target.value)}
      />
      <TextField
        type="datetime-local"
        label={t("community:events.form.endsAt")}
        value={endsAt}
        onChange={(e) => setEndsAt(e.target.value)}
      />
      <CheckboxField
        label={t("community:events.form.allDay")}
        checked={allDay}
        onChange={(e) => setAllDay(e.target.checked)}
      />
      <TextField
        label={t("community:events.form.timezone")}
        value={zone}
        required
        onChange={(e) => setZone(e.target.value)}
      />
      <SelectField
        label={t("community:events.form.audience")}
        value={audience}
        onChange={(e) => setAudience(e.target.value as CommunityEventInput["audience"])}
      >
        {(["public", "community", "roles"] as const).map((value) => (
          <option key={value} value={value}>
            {t(`community:events.audience.${value}`)}
          </option>
        ))}
      </SelectField>
      {audience === "roles" ? (
        <TextField
          label={t("community:events.form.roles")}
          value={roles}
          onChange={(e) => setRoles(e.target.value)}
        />
      ) : null}
      {save.isError ? <p role="alert">{t("community:events.error")}</p> : null}
      <div className="ds-stack--row">
        <Button type="submit" disabled={save.isPending}>
          {t("community:events.form.save")}
        </Button>
        <Button type="button" variant="secondary" onClick={onDone}>
          {t("community:events.form.close")}
        </Button>
      </div>
    </form>
  );
}
