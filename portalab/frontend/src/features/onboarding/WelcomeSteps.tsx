import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { Switch } from "../account/SettingsKit";
import { useLinkActions, useLinks } from "../media/api";
import { useServices } from "../media/links/LinksSettings";
import { NewsletterSubscriptions } from "../news/NewsletterSubscriptions";
import { type Preferences, usePreferences, useSavePreferences } from "../notifications/api";
import {
  type Category,
  CHANNELS,
  COMPANIONS,
  GROUPS,
  groupOf,
  SHOWN_WITH,
} from "../notifications/preferences/NotificationPreferences";
import { connectorIcon } from "../services/connectorIcons";

/**
 * Issue 347: two screens of the welcome — the media accounts (so that what the member watches counts), and
 * how they are told (one switch per theme, on the portal and by e-mail, a ready-made choice, the e-mails'
 * pace, the newsletters). Everything is saved as it is changed; « Next » only goes on.
 */

/** The member's accounts on the media services: linked, verified or not, and one more to link. */
export function Accounts({ titleId, nav }: { titleId: string; nav: ReactNode }) {
  const t = useT();
  const links = useLinks();
  const services = useServices();
  const { add, verify } = useLinkActions();
  const [service, setService] = useState("");
  const [account, setAccount] = useState("");
  const [proofs, setProofs] = useState<Record<string, string>>({});
  const items = links.data ?? [];
  const nameOf = (id: string) => services.data?.find((s) => s.id === id);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate(
      { service_id: service.trim(), external_user_id: account.trim() },
      { onSuccess: () => setAccount("") },
    );
  };
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:accounts.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:accounts.lead")}</p>
      <ul className="onboarding-accounts">
        {items.map((link) => {
          const known = nameOf(link.service_id);
          return (
            <li key={link.id} data-verified={link.verified || undefined}>
              <Icon name={connectorIcon(known?.connector)} size={18} />
              <span className="onboarding-accounts__name">
                <strong>{known?.name ?? t("account:media.service")}</strong>
                <span className="onboarding-accounts__who">
                  {t("account:media.as", { account: link.external_user_id })}
                </span>
              </span>
              <span className="onboarding-accounts__state">
                <Icon name={link.verified ? "check" : "clock"} size={14} />
                {link.verified ? t("media:links.verified") : t("media:links.unverified")}
              </span>
              {link.verified ? null : (
                <form
                  className="onboarding-accounts__proof"
                  onSubmit={(event) => {
                    event.preventDefault();
                    verify.mutate({ id: link.id, proof: proofs[link.id] ?? "" });
                  }}
                >
                  <TextField
                    label={t("media:links.proof")}
                    value={proofs[link.id] ?? ""}
                    onChange={(e) => setProofs({ ...proofs, [link.id]: e.target.value })}
                  />
                  <Button type="submit" variant="secondary">
                    {t("media:links.verify")}
                  </Button>
                </form>
              )}
            </li>
          );
        })}
        {links.isSuccess && !items.length ? (
          <li className="onboarding-accounts__none">{t("onboarding:accounts.none")}</li>
        ) : null}
      </ul>
      {services.data?.length ? (
        <form className="onboarding-accounts__add" onSubmit={submit}>
          <SelectField
            label={t("media:links.service")}
            value={service}
            onChange={(e) => setService(e.target.value)}
            required
          >
            <option value="">{t("account:media.choose")}</option>
            {services.data.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("media:links.account")}
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            required
          />
          <Button type="submit" variant="secondary" disabled={add.isPending}>
            <Icon name="link" size={16} />
            {t("media:links.add")}
          </Button>
        </form>
      ) : null}
      {add.isError || verify.isError ? (
        <p className="onboarding-welcome__problem" role="alert">
          {t("onboarding:accounts.error")}
        </p>
      ) : null}
      <p className="onboarding-welcome__hint">
        {t("onboarding:accounts.later")}{" "}
        <Link to="/settings/media-accounts">{t("onboarding:accounts.settings")}</Link>
      </p>
      {nav}
    </>
  );
}

const PRESETS = ["all", "essential", "minimum"] as const;
type Preset = (typeof PRESETS)[number];
/** Issue 347: the ready-made choice the portal recommends. */
const RECOMMENDED: Preset = "essential";
/** What each ready-made choice keeps: the themes told on the portal, those told by e-mail too, the pace. */
const KEEPS: Record<
  Preset,
  { portal: readonly string[] | "all"; email: readonly string[] | "all"; digest: Preferences["digest"] }
> = {
  all: { portal: "all", email: "all", digest: "off" },
  essential: { portal: "all", email: ["account", "media", "support"], digest: "daily" },
  minimum: { portal: ["account", "media", "support"], email: ["account"], digest: "weekly" },
};

/** A category's switch the member may turn (not required, not locked by the administrator). */
const free = (category: Category, channel: string) => {
  const state = category.channels[channel as keyof Category["channels"]];
  return state && !state.mandatory && !state.locked ? state : null;
};

/** The keys a line stands for (issue 124: a category and its « e-mail » companion are one line). */
const keysOf = (category: Category) => [
  category.key,
  ...(COMPANIONS[category.key] ? [COMPANIONS[category.key] as string] : []),
];

/** How the member is told: a ready-made choice, a switch per theme and channel, the e-mails' pace, the
 * newsletters. */
export function Notify({
  titleId,
  first,
  onNext,
  renderNav,
}: {
  titleId: string;
  first: boolean;
  onNext: () => void;
  renderNav: (go: () => void) => ReactNode;
}) {
  const t = useT();
  const query = usePreferences();
  const save = useSavePreferences();
  // the recommended choice offered on a first visit, applied on « Next » unless the member set something
  const [preset, setPreset] = useState<Preset | null>(first ? RECOMMENDED : null);
  const [touched, setTouched] = useState(false);
  const data = query.data;
  const lines = (data?.categories ?? []).filter((c) => !SHOWN_WITH.has(c.key));
  const groups = GROUPS.map((group) => ({
    ...group,
    lines: lines.filter((c) => groupOf(c) === group.key),
  })).filter((group) => group.lines.some((c) => CHANNELS.some((channel) => c.channels[channel])));
  const set = (targets: Category[], channel: string, on: boolean) => {
    const changes = targets.filter((c) => free(c, channel));
    if (!changes.length) return;
    save.mutate({
      preferences: Object.fromEntries(
        changes.flatMap((c) => keysOf(c).map((key) => [key, { [channel]: on }])),
      ),
    });
  };
  const apply = (choice: Preset) => {
    setPreset(choice);
    setTouched(true);
    const keep = KEEPS[choice];
    const wants = (rule: readonly string[] | "all", group: string) => rule === "all" || rule.includes(group);
    const preferences: Record<string, Record<string, boolean>> = {};
    for (const category of lines) {
      const group = groupOf(category);
      for (const channel of CHANNELS) {
        if (!free(category, channel)) continue;
        for (const key of keysOf(category)) {
          preferences[key] = { ...(preferences[key] ?? {}), [channel]: wants(keep[channel], group) };
        }
      }
    }
    save.mutate({ preferences, digest: keep.digest });
  };
  return (
    <>
      <DialogPrimitive.Title id={titleId}>{t("onboarding:notify.title")}</DialogPrimitive.Title>
      <p className="onboarding-welcome__lead">{t("onboarding:notify.lead")}</p>
      <fieldset className="onboarding-presets" disabled={!data || save.isPending}>
        <legend className="visually-hidden">{t("onboarding:notify.presets")}</legend>
        {PRESETS.map((choice) => (
          <label key={choice} className="onboarding-tile" data-current={preset === choice || undefined}>
            <input
              type="radio"
              name="onboarding-notify"
              checked={preset === choice}
              onChange={() => apply(choice)}
            />
            <strong>{t(`onboarding:notify.preset.${choice}`)}</strong>
            {choice === RECOMMENDED ? (
              <span className="onboarding-tile__badge">{t("onboarding:recommended")}</span>
            ) : null}
            <span>{t(`onboarding:notify.preset.${choice}Hint`)}</span>
          </label>
        ))}
      </fieldset>
      {data ? (
        <table className="onboarding-notify">
          <thead>
            <tr>
              <th scope="col">
                <span className="visually-hidden">{t("onboarding:notify.theme")}</span>
              </th>
              {CHANNELS.map((channel) => (
                <th key={channel} scope="col">
                  {t(`notifications:preferences.${channel}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => {
              const label = t(`account:notifications.group.${group.key}`);
              return (
                <tr key={group.key}>
                  <th scope="row">
                    <span className="onboarding-notify__icon">
                      <Icon name={group.icon} size={16} />
                    </span>
                    {label}
                  </th>
                  {CHANNELS.map((channel) => {
                    const own = group.lines.filter((c) => c.channels[channel]);
                    if (!own.length) return <td key={channel} />;
                    const turnable = own.some((c) => free(c, channel));
                    const id = `onboarding-notify-${group.key}-${channel}`;
                    return (
                      <td key={channel}>
                        <Switch
                          id={id}
                          hideLabel
                          label={`${label}: ${t(`notifications:preferences.${channel}`)}`}
                          checked={own.some((c) => c.channels[channel]?.enabled)}
                          disabled={!turnable || save.isPending}
                          onChange={(event) => {
                            setPreset(null);
                            setTouched(true);
                            set(own, channel, event.currentTarget.checked);
                          }}
                        />
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
      {data ? (
        <SelectField
          label={t("notifications:preferences.digest")}
          value={data.digest}
          onChange={(event) => save.mutate({ digest: event.currentTarget.value as Preferences["digest"] })}
        >
          {(["off", "daily", "weekly"] as const).map((mode) => (
            <option key={mode} value={mode}>
              {t(`notifications:preferences.digest.${mode}`)}
            </option>
          ))}
        </SelectField>
      ) : null}
      <div className="onboarding-newsletters">
        <NewsletterSubscriptions />
      </div>
      {save.isError ? (
        <p className="onboarding-welcome__problem" role="alert">
          {t("onboarding:notify.error")}
        </p>
      ) : null}
      <p className="onboarding-welcome__hint">
        {t("onboarding:notify.later")}{" "}
        <Link to="/settings/notifications">{t("onboarding:notify.settings")}</Link>
      </p>
      {renderNav(() => {
        if (first && !touched && data && preset === RECOMMENDED) apply(RECOMMENDED);
        onNext();
      })}
    </>
  );
}
