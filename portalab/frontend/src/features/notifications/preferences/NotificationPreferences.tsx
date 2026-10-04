import { useId, useState } from "react";
import { SelectField } from "../../../design-system/components/Field";
import { PolicyField } from "../../../design-system/components/PolicyField";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type Preferences, usePreferences, useSavePreferences } from "../api";
import "../notifications.css";
import { PageHeader } from "../../../design-system/components/PageHeader";

/**
 * Notification preferences (spec 010 T016): per category and channel; a channel required by the category
 * or by the administrator is shown checked and explained (``PolicyField``), never silently disabled; a
 * category the administrator locked is read-only; the e-mail digest mode.
 */
const CHANNELS = ["portal", "email"] as const;

function Row({
  category,
  onToggle,
}: {
  category: Preferences["categories"][number];
  onToggle: (channel: string, on: boolean) => void;
}) {
  const t = useT();
  const rowId = useId();
  const label = t(category.label_key);
  return (
    <tr>
      <th scope="row">{label}</th>
      {CHANNELS.map((channel) => {
        const state = category.channels[channel];
        if (!state) return <td key={channel} />;
        const policy = state.mandatory ? "mandatory" : state.locked ? "locked" : "free";
        const id = `${rowId}-${channel}`;
        return (
          <td key={channel}>
            <PolicyField id={id} state={policy}>
              {({ disabled, describedBy }) => (
                <input
                  id={id}
                  type="checkbox"
                  checked={state.enabled}
                  disabled={disabled || state.mandatory}
                  aria-describedby={describedBy}
                  aria-label={`${label}: ${t(`notifications:preferences.${channel}`)}`}
                  onChange={(event) => onToggle(channel, event.currentTarget.checked)}
                />
              )}
            </PolicyField>
          </td>
        );
      })}
    </tr>
  );
}

export function NotificationPreferences() {
  const t = useT();
  const headingId = useId();
  const query = usePreferences();
  const save = useSavePreferences();
  const [saved, setSaved] = useState(false);
  if (query.isPending) return <FunctionalState state="loading" />;
  if (query.isError || !query.data)
    return <FunctionalState state="unavailable" onRetry={() => query.refetch()} />;
  const data = query.data;
  const submit = (body: Parameters<typeof save.mutate>[0]) =>
    save.mutate(body, { onSuccess: () => setSaved(true), onError: () => setSaved(false) });
  return (
    <section aria-labelledby={headingId} className="notification-preferences">
      <PageHeader titleId={headingId} level={2} icon="bell" title={t("notifications:preferences.title")} />
      <table>
        <thead>
          <tr>
            <td />
            {CHANNELS.map((channel) => (
              <th key={channel} scope="col">
                {t(`notifications:preferences.${channel}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.categories.map((category) => (
            <Row
              key={category.key}
              category={category}
              onToggle={(channel, on) => submit({ preferences: { [category.key]: { [channel]: on } } })}
            />
          ))}
        </tbody>
      </table>
      <SelectField
        label={t("notifications:preferences.digest")}
        value={data.digest}
        onChange={(event) => submit({ digest: event.currentTarget.value as Preferences["digest"] })}
      >
        {(["off", "daily", "weekly"] as const).map((mode) => (
          <option key={mode} value={mode}>
            {t(`notifications:preferences.digest.${mode}`)}
          </option>
        ))}
      </SelectField>
      <p aria-live="polite">{saved ? t("notifications:preferences.saved") : ""}</p>
      {save.isError ? <FunctionalState state="error" /> : null}
    </section>
  );
}

export default NotificationPreferences;
