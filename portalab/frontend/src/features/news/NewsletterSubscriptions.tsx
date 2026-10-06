import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import "./news.css";

interface Subscription {
  key: string;
  name: string;
  description: string;
  icon: string | null;
  subscribed: boolean;
}

const KEY = ["me", "newsletters"] as const;

/**
 * Newsletters I receive by e-mail (027): one switch per channel the news desk sends by e-mail — every
 * member is subscribed until they unsubscribe; the e-mails' « unsubscribe » link leads here.
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
  return (
    <section id="newsletters" className="newsletter-subscriptions" aria-labelledby="newsletters-title">
      <h3 id="newsletters-title">
        <Icon name="mail" size={18} />
        {t("news:subscriptions.title")}
      </h3>
      <p className="ds-page-header__context">{t("news:subscriptions.hint")}</p>
      <ul>
        {channels.data.map((channel) => (
          <li key={channel.key} data-on={channel.subscribed || undefined}>
            <span className="newsletter-subscriptions__icon" aria-hidden="true">
              <Icon name={channel.icon ?? "newspaper"} size={18} />
            </span>
            <label className="newsletter-subscriptions__text" htmlFor={`newsletter-${channel.key}`}>
              <strong>{channel.name}</strong>
              {channel.description ? <span>{channel.description}</span> : null}
            </label>
            <input
              id={`newsletter-${channel.key}`}
              type="checkbox"
              role="switch"
              aria-checked={channel.subscribed}
              checked={channel.subscribed}
              disabled={change.isPending}
              onChange={(event) => change.mutate({ [channel.key]: event.target.checked })}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
