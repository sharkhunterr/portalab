import { type FormEvent, useEffect, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { useT } from "../../../i18n/hooks/useT";
import { type AiConfig, type AiConfigUpdate, useAiAdmin, useAiConfig, useAiUsage } from "../api";

/**
 * Assistant settings (spec 018 T031, ``ai.manage``): provider, limits and tools; the provider credential is
 * write-only (only "a credential is stored" is shown); provider test; usage aggregates without content.
 */
const NUMBERS = [
  ["max_tool_calls_per_turn", "ai:admin.maxToolCalls"],
  ["request_timeout_seconds", "ai:admin.timeout"],
  ["daily_token_budget_per_user", "ai:admin.budget"],
  ["rate_limit_per_minute", "ai:admin.rate"],
  ["retention_days", "ai:admin.retention"],
  ["pending_action_ttl_minutes", "ai:admin.pendingTtl"],
] as const;

type Values = Record<string, unknown>;

export function AiSettings() {
  const t = useT();
  const config = useAiConfig();
  const usage = useAiUsage();
  const { save, test } = useAiAdmin();
  const [values, setValues] = useState<Values>({});
  const [access, setAccess] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (config.data) setValues({ ...(config.data.values as Values) });
  }, [config.data]);
  if (!config.data) return null;
  const data: AiConfig = config.data;
  const disabled = new Set((values.tools_disabled as string[] | undefined) ?? []);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const body: AiConfigUpdate = {
      enabled: Boolean(values.enabled),
      provider_endpoint: String(values.provider_endpoint ?? ""),
      provider_model: String(values.provider_model ?? ""),
      auto_navigate: Boolean(values.auto_navigate),
      tools_disabled: [...disabled],
      ...Object.fromEntries(NUMBERS.map(([key]) => [key, Number(values[key])])),
      ...(access ? { provider_secret: access } : {}),
    };
    save.mutate(body, {
      onSuccess: () => {
        setAccess("");
        setSaved(true);
      },
    });
  };
  return (
    <section aria-labelledby="ai-settings-title">
      <PageHeader titleId="ai-settings-title" level={2} icon="sparkles" title={t("ai:admin.title")} />
      <form className="ds-stack" onSubmit={submit}>
        <CheckboxField
          label={t("ai:admin.enabled")}
          checked={Boolean(values.enabled)}
          onChange={(event) => setValues({ ...values, enabled: event.target.checked })}
        />
        <TextField
          label={t("ai:admin.endpoint")}
          type="url"
          value={String(values.provider_endpoint ?? "")}
          onChange={(event) => setValues({ ...values, provider_endpoint: event.target.value })}
        />
        <TextField
          label={t("ai:admin.model")}
          value={String(values.provider_model ?? "")}
          onChange={(event) => setValues({ ...values, provider_model: event.target.value })}
        />
        <TextField
          label={t("ai:admin.access")}
          type="password"
          autoComplete="off"
          value={access}
          hint={
            data.provider_secret_set ? `${t("ai:admin.accessSet")} ${t("ai:admin.accessHint")}` : undefined
          }
          onChange={(event) => setAccess(event.target.value)}
        />
        {NUMBERS.map(([key, label]) => (
          <TextField
            key={key}
            label={t(label)}
            type="number"
            min={0}
            value={String(values[key] ?? "")}
            onChange={(event) => setValues({ ...values, [key]: event.target.value })}
          />
        ))}
        <CheckboxField
          label={t("ai:admin.autoNavigate")}
          checked={Boolean(values.auto_navigate)}
          onChange={(event) => setValues({ ...values, auto_navigate: event.target.checked })}
        />
        <fieldset>
          <legend>{t("ai:admin.tools")}</legend>
          {data.tools.map((tool) => (
            <CheckboxField
              key={tool.name}
              label={`${t("ai:admin.tool.enabled", { tool: tool.name })} — ${t(`ai:admin.sensitivity.${tool.sensitivity}`)}`}
              checked={!disabled.has(tool.name)}
              disabled={tool.sensitivity === "ai_forbidden"}
              onChange={(event) => {
                const next = new Set(disabled);
                if (event.target.checked) next.delete(tool.name);
                else next.add(tool.name);
                setValues({ ...values, tools_disabled: [...next] });
              }}
            />
          ))}
        </fieldset>
        <div className="ds-stack--row">
          <Button type="submit" disabled={save.isPending}>
            {t("ai:admin.save")}
          </Button>
          <Button type="button" variant="secondary" onClick={() => test.mutate()} disabled={test.isPending}>
            {t("ai:admin.test")}
          </Button>
        </div>
        {saved ? <p role="status">{t("ai:admin.saved")}</p> : null}
        {test.data ? (
          <p role="status">
            {test.data.ok
              ? t("ai:admin.testOk", { ms: test.data.latency_ms })
              : t("ai:admin.testFailed", { code: test.data.code ?? "" })}
          </p>
        ) : null}
      </form>
      <h3>{t("ai:admin.usage")}</h3>
      <table className="ai-admin-table">
        <thead>
          <tr>
            <th scope="col">{t("ai:admin.usage.day")}</th>
            <th scope="col">{t("ai:admin.usage.users")}</th>
            <th scope="col">{t("ai:admin.usage.requests")}</th>
            <th scope="col">{t("ai:admin.usage.volume")}</th>
          </tr>
        </thead>
        <tbody>
          {(usage.data?.days ?? []).map((day) => (
            <tr key={String(day.day)}>
              <td>{String(day.day)}</td>
              <td>{String(day.users)}</td>
              <td>{String(day.requests)}</td>
              <td>{Number(day.tokens_in) + Number(day.tokens_out)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
