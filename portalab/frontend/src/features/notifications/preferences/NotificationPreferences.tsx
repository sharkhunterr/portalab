import { useState } from "react";
import { SelectField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { PolicyField } from "../../../design-system/components/PolicyField";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { SavedNote, SettingsCard, SettingsGrid, SettingsPage, Switch } from "../../account/SettingsKit";
import { NewsletterSubscriptions } from "../../news/NewsletterSubscriptions";
import { type Preferences, usePreferences, useSavePreferences } from "../api";
import "../notifications.css";

/**
 * Notification preferences (spec 010 T016; #46 redrawn like the other « My account » tabs): one card per
 * theme (account, media, community…), a switch per channel; a channel required by the category or by the
 * administrator is shown on and explained (``PolicyField``), never silently disabled; a category the
 * administrator locked is read-only; the e-mail digest in a card of its own. Issue 124: a category and its
 * « e-mail » companion (the same thing, sent by e-mail too when the administrator's rule says so) are one
 * line — its switches set both.
 */
const CHANNELS = ["portal", "email"] as const;
type Category = Preferences["categories"][number];

/** Which card a category goes in, from its key's prefix (« media.available » → media). */
const GROUPS: ReadonlyArray<{ key: string; icon: string; prefixes: readonly string[] }> = [
  { key: "account", icon: "shield", prefixes: ["account"] },
  { key: "media", icon: "film", prefixes: ["media"] },
  { key: "community", icon: "users", prefixes: ["community", "campaigns"] },
  { key: "progression", icon: "trophy", prefixes: ["gamification", "statistics"] },
  { key: "shop", icon: "shop", prefixes: ["marketplace"] },
  { key: "news", icon: "newspaper", prefixes: ["news", "communications", "calendar"] },
  { key: "support", icon: "lifebuoy", prefixes: ["support", "system"] },
  { key: "admin", icon: "settings", prefixes: ["automations", "plugins"] },
];

/** Issue 124: the category a companion is shown with — one line for the member, two keys behind it. */
const COMPANIONS: Record<string, string> = {
  "system.health": "system.health_email",
  "communications.broadcast": "communications.announcement_email",
};
const SHOWN_WITH = new Set(Object.values(COMPANIONS));

/** The line of a category with its companion: portal as the category says, e-mail as the companion does. */
function merged(category: Category, all: readonly Category[]): { line: Category; keys: string[] } {
  const companion = all.find((c) => c.key === COMPANIONS[category.key]);
  if (!companion) return { line: category, keys: [category.key] };
  const email = companion.channels.email ?? category.channels.email;
  const channels = email ? { ...category.channels, email } : category.channels;
  return { line: { ...category, channels }, keys: [category.key, companion.key] };
}

function groupOf(category: Category): string {
  const prefix = category.key.split(".")[0] ?? "";
  return GROUPS.find((group) => group.prefixes.includes(prefix))?.key ?? "other";
}

function Line({
  category,
  onToggle,
}: {
  category: Category;
  onToggle: (channel: string, on: boolean) => void;
}) {
  const t = useT();
  const label = t(category.label_key);
  return (
    <li>
      <span className="settings-list__text">
        <strong>{label}</strong>
        {Object.values(category.channels).some((state) => state?.mandatory || state?.locked) ? (
          <span>
            <Icon name="lock" size={12} /> {t("account:notifications.locked")}
          </span>
        ) : null}
      </span>
      <span className="settings-list__controls">
        {CHANNELS.map((channel) => {
          const state = category.channels[channel];
          if (!state) return <span key={channel} className="notif-matrix__cell" />;
          const policy = state.mandatory ? "mandatory" : state.locked ? "locked" : "free";
          const id = `notif-${category.key}-${channel}`;
          return (
            <span key={channel} className="notif-matrix__cell">
              <PolicyField id={id} state={policy}>
                {({ disabled, describedBy }) => (
                  <Switch
                    id={id}
                    hideLabel
                    label={`${label}: ${t(`notifications:preferences.${channel}`)}`}
                    checked={state.enabled}
                    disabled={disabled || state.mandatory}
                    aria-describedby={describedBy}
                    onChange={(event) => onToggle(channel, event.currentTarget.checked)}
                  />
                )}
              </PolicyField>
            </span>
          );
        })}
      </span>
    </li>
  );
}

export function NotificationPreferences() {
  const t = useT();
  const query = usePreferences();
  const save = useSavePreferences();
  const [saved, setSaved] = useState(false);
  if (query.isPending) return <FunctionalState state="loading" />;
  if (query.isError || !query.data)
    return <FunctionalState state="unavailable" onRetry={() => query.refetch()} />;
  const data = query.data;
  const submit = (body: Parameters<typeof save.mutate>[0]) =>
    save.mutate(body, { onSuccess: () => setSaved(true), onError: () => setSaved(false) });
  const groups = [...GROUPS, { key: "other", icon: "bell", prefixes: [] }]
    .map((group) => ({
      ...group,
      items: data.categories.filter((c) => groupOf(c) === group.key && !SHOWN_WITH.has(c.key)),
    }))
    .filter((group) => group.items.length);
  const heads = (
    <span className="notif-matrix__head" aria-hidden="true">
      {CHANNELS.map((channel) => (
        <span key={channel}>{t(`notifications:preferences.${channel}`)}</span>
      ))}
    </span>
  );
  return (
    <SettingsPage
      icon="bell"
      title={t("notifications:preferences.title")}
      lead={t("account:notifications.lead")}
      actions={<SavedNote shown={saved} text={t("notifications:preferences.saved")} />}
      className="notification-preferences"
    >
      {save.isError ? <FunctionalState state="error" /> : null}
      <SettingsGrid>
        {groups.map((group) => (
          <SettingsCard
            key={group.key}
            icon={group.icon}
            title={t(`account:notifications.group.${group.key}`)}
            aside={heads}
          >
            <ul className="settings-list">
              {group.items.map((category) => {
                const { line, keys } = merged(category, data.categories);
                return (
                  <Line
                    key={category.key}
                    category={line}
                    onToggle={(channel, on) =>
                      submit({
                        preferences: Object.fromEntries(keys.map((key) => [key, { [channel]: on }])),
                      })
                    }
                  />
                );
              })}
            </ul>
          </SettingsCard>
        ))}
        <SettingsCard
          icon="mail"
          title={t("notifications:preferences.digest")}
          hint={t("account:notifications.digestHint")}
        >
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
        </SettingsCard>
      </SettingsGrid>
      <NewsletterSubscriptions />
    </SettingsPage>
  );
}

export default NotificationPreferences;
