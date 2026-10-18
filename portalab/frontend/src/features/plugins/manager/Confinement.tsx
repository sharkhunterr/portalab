import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { putSecret, useConfinement, usePluginActions } from "../api";

function capabilityLabel(t: ReturnType<typeof useT>, name: string, fallback: string): string {
  const key = `plugins:capability.${name}`;
  const text = t(key);
  return text === key ? fallback : text;
}

function SecretRow({
  plugin,
  name,
  description,
  set,
}: {
  plugin: string;
  name: string;
  description: string;
  set: boolean;
}) {
  const t = useT();
  const client = useQueryClient();
  const action = usePluginActions();
  const [value, setValue] = useState("");
  const [failed, setFailed] = useState(false);
  const save = async () => {
    setFailed(false);
    try {
      await putSecret(plugin, name, value, () => window.confirm(t("plugins:confined.confirmKept", { name })));
      setValue("");
      await client.invalidateQueries({ queryKey: ["plugins"] });
    } catch {
      setFailed(true);
    }
  };
  return (
    <li className="ds-stack">
      <p>
        <strong>{name}</strong> — {description} ·{" "}
        {set ? t("plugins:confined.keptOn") : t("plugins:confined.keptOff")}
      </p>
      <div className="ds-stack--row">
        <TextField
          label={t("plugins:confined.keptValue", { name })}
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <Button variant="secondary" disabled={!value} onClick={save}>
          {set ? t("plugins:confined.replace") : t("plugins:confined.set")}
        </Button>
        {set ? (
          <Button
            variant="ghost"
            onClick={() =>
              action.mutate({
                path: `/api/v1/admin/plugins/${plugin}/secrets/${name}/clear`,
                confirm: () => window.confirm(t("plugins:confined.confirmClear", { name })),
              })
            }
          >
            {t("plugins:confined.clear")}
          </Button>
        ) : null}
      </div>
      {failed ? <p role="alert">{t("plugins:confined.keptFailed")}</p> : null}
    </li>
  );
}

/**
 * 030: how a plugin runs — confined (the kernel and Portalab bound it), in Portalab's process (a permanent
 * warning) or in the weaker mode — what it was granted (revocable at once), what it tried and was refused,
 * the hosts it reaches and its secret settings (write-only).
 */
export function Confinement({ pluginKey }: { pluginKey: string }) {
  const t = useT();
  const format = useFormat();
  const query = useConfinement(pluginKey);
  const action = usePluginActions();
  if (query.isPending) return <FunctionalState state="loading" />;
  if (query.isError || !query.data)
    return <FunctionalState state="unavailable" onRetry={() => query.refetch()} />;
  const data = query.data;
  return (
    <section className="ds-card ds-stack" aria-labelledby={`confinement-${pluginKey}`}>
      <h3 id={`confinement-${pluginKey}`}>{t("plugins:confined.title")}</h3>
      <p>{t(`plugins:confined.runtime.${data.runtime}`)}</p>
      {data.warning ? (
        <p role="alert" className="maintenance-banner">
          {t(`plugins:confined.warning.${data.warning}`)}
        </p>
      ) : null}
      {data.runtime === "confined" ? (
        <>
          <h4>{t("plugins:confined.grants")}</h4>
          <ul className="ds-stack">
            {data.grants.map((grant) => (
              <li key={grant.capability} className="ds-stack--row">
                <span>
                  {capabilityLabel(t, grant.capability, grant.description)}
                  {grant.revoked_at ? ` · ${t("plugins:confined.revoked")}` : ""}
                </span>
                {grant.revoked_at ? null : (
                  <Button
                    variant="ghost"
                    onClick={() =>
                      action.mutate({
                        path: `/api/v1/admin/plugins/${pluginKey}/grants/${grant.capability}/revoke`,
                        confirm: () => window.confirm(t("plugins:confined.confirmRevoke")),
                      })
                    }
                  >
                    {t("plugins:confined.revoke")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {data.network.hosts.length ? (
            <>
              <h4>{t("plugins:confined.hosts")}</h4>
              <ul>
                {data.network.hosts.map((host) => {
                  const counted = data.network.last_24h[host.host];
                  return (
                    <li key={`${host.host}:${host.port}`}>
                      {host.scheme}://{host.host}:{host.port}
                      {host.private ? ` · ${t("plugins:confined.private")}` : ""}
                      {counted ? ` · ${t("plugins:confined.calls", { count: counted.calls })}` : ""}
                    </li>
                  );
                })}
              </ul>
            </>
          ) : null}
          {data.secrets.length ? (
            <>
              <h4>{t("plugins:confined.keptSettings")}</h4>
              <ul className="ds-stack">
                {data.secrets.map((secret) => (
                  <SecretRow key={secret.name} plugin={pluginKey} {...secret} />
                ))}
              </ul>
            </>
          ) : null}
        </>
      ) : null}
      <h4>{t("plugins:confined.attempts")}</h4>
      {data.attempts.length === 0 ? (
        <p>{t("plugins:confined.noAttempt")}</p>
      ) : (
        <ul>
          {data.attempts.map((attempt, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: attempts are listed as recorded
            <li key={index}>
              {format.dateTime(attempt.occurred_at)} · {t(`plugins:attempt.${attempt.kind}`)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
