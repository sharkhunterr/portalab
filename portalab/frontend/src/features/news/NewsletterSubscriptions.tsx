import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { SettingsCard, Switch } from "../account/SettingsKit";
import "./news.css";

interface Subscription {
  key: string;
  /** issue 326: an automatic newsletter, or a channel */
  kind?: "automatic" | "channel";
  name: string;
  description: string;
  icon: string | null;
  /** an automatic newsletter's channel (left, the newsletter is left too) */
  channel?: string | null;
  subscribed: boolean;
}

const capital = (text: string) => (text ? text[0]?.toLocaleUpperCase() + text.slice(1) : text);

const KEY = ["me", "newsletters"] as const;

/**
 * Newsletters I receive by e-mail (027): one switch per channel the news desk sends by e-mail — every
 * member is subscribed until they unsubscribe; the e-mails' « unsubscribe » link leads here. Issue 326:
 * first the automatic newsletters, each with when it goes out, left one without the others (leaving a
 * channel leaves its newsletters too).
 */
export function NewsletterSubscriptions() {
  const t = useT();
  const client = useQueryClient();
  const channels = useQuery({
    queryKey: KEY,
    retry: false,
    queryFn: async () => ((await api.GET("/api/v1/me/newsletters")).data ?? []) as unknown as Subscription[],
  });
  const change = useMutation({
    mutationFn: async (changes: Record<string, boolean>) =>
      ((await api.PUT("/api/v1/me/newsletters", { body: { changes } })).data ??
        []) as unknown as Subscription[],
    onSuccess: (data) => client.setQueryData(KEY, data),
  });
  if (!channels.data?.length) return null;
  const all = channels.data;
  const byKey = new Map(all.map((item) => [item.key, item]));
  const groups: Array<[string, Subscription[]]> = [
    ["automatic", all.filter((item) => item.kind === "automatic")],
    ["channels", all.filter((item) => item.kind !== "automatic")],
  ];
  return (
    <SettingsCard
      id="newsletters"
      icon="mail"
      title={t("news:subscriptions.title")}
      hint={t("news:subscriptions.hint")}
    >
      {groups.map(([group, items]) =>
        items.length ? (
          <section key={group} className="newsletter-group">
            <h4 className="newsletter-group__title">{t(`news:subscriptions.${group}`)}</h4>
            <ul className="settings-list">
              {items.map((item) => {
                const channel = item.channel ? byKey.get(item.channel) : undefined;
                const blocked = Boolean(channel && !channel.subscribed);
                return (
                  <li key={item.key} data-on={item.subscribed || undefined}>
                    <span className="linked-service" aria-hidden="true">
                      <Icon name={item.icon ?? "newspaper"} size={18} />
                    </span>
                    <span className="settings-list__text">
                      <strong>{item.name}</strong>
                      {item.description ? (
                        <span>
                          {item.kind === "automatic" ? capital(item.description) : item.description}
                        </span>
                      ) : null}
                      {blocked && channel ? (
                        <span>{t("news:subscriptions.byChannel", { channel: channel.name })}</span>
                      ) : null}
                    </span>
                    <Switch
                      id={`newsletter-${item.key}`}
                      hideLabel
                      label={item.name}
                      role="switch"
                      aria-checked={item.subscribed}
                      checked={item.subscribed}
                      disabled={change.isPending || blocked}
                      onChange={(event) => change.mutate({ [item.key]: event.target.checked })}
                    />
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null,
      )}
    </SettingsCard>
  );
}
