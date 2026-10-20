import { type FormEvent, useEffect, useState } from "react";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextAreaField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { type AiConfig, type AiConfigUpdate, useAiAdmin, useAiConfig, useAiUsage } from "../api";
import { IDEAS } from "../panel/AiPanel";
import { ModelServer } from "./ModelServer";
import { ToolChoice } from "./ToolChoice";

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

/** issue 174: the questions offered to start with — one a line, eight at most */
function ideasOf(value: unknown): string[] {
  const lines = Array.isArray(value) ? value.map(String) : String(value ?? "").split("\n");
  return lines
    .map((line) => line.trim().slice(0, 120))
    .filter(Boolean)
    .slice(0, 8);
}

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
      provider_reasoning: String(values.provider_reasoning ?? "") as "" | "none" | "low" | "medium" | "high",
      assistant_name: String(values.assistant_name ?? "").trim(),
      assistant_role: String(values.assistant_role ?? "").trim(),
      assistant_fallback: String(values.assistant_fallback ?? "").trim(),
      assistant_ideas: ideasOf(values.assistant_ideas),
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
    <AdminSection title={t("ai:admin.settings")} icon="settings">
      <form className="ds-stack" onSubmit={submit}>
        <CheckboxField
          label={t("ai:admin.enabled")}
          checked={Boolean(values.enabled)}
          onChange={(event) => setValues({ ...values, enabled: event.target.checked })}
        />
        <ModelServer values={values} onChange={setValues} />
        <fieldset className="ai-persona">
          <legend>
            <Icon name="sparkles" size={16} /> {t("ai:admin.persona.title")}
          </legend>
          <TextField
            label={t("ai:admin.persona.name")}
            hint={t("ai:admin.persona.nameHint")}
            placeholder="Nova"
            maxLength={40}
            value={String(values.assistant_name ?? "")}
            onChange={(event) => setValues({ ...values, assistant_name: event.target.value })}
          />
          <TextAreaField
            label={t("ai:admin.persona.role")}
            hint={t("ai:admin.persona.roleHint")}
            rows={3}
            maxLength={800}
            value={String(values.assistant_role ?? "")}
            onChange={(event) => setValues({ ...values, assistant_role: event.target.value })}
          />
          <TextAreaField
            label={t("ai:admin.persona.fallback")}
            hint={t("ai:admin.persona.fallbackHint")}
            rows={3}
            maxLength={800}
            value={String(values.assistant_fallback ?? "")}
            onChange={(event) => setValues({ ...values, assistant_fallback: event.target.value })}
          />
          <TextAreaField
            label={t("ai:admin.persona.ideas")}
            hint={t("ai:admin.persona.ideasHint")}
            rows={4}
            placeholder={IDEAS.map((idea) => t(`ai:panel.idea.${idea}`)).join("\n")}
            value={
              Array.isArray(values.assistant_ideas)
                ? values.assistant_ideas.join("\n")
                : String(values.assistant_ideas ?? "")
            }
            onChange={(event) => setValues({ ...values, assistant_ideas: event.target.value })}
          />
        </fieldset>
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
        <div className="ai-tools-section">
          <h3>{t("ai:admin.tools")}</h3>
          <ToolChoice
            tools={data.tools}
            disabled={disabled}
            onChange={(next) => setValues({ ...values, tools_disabled: [...next] })}
          />
        </div>
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
    </AdminSection>
  );
}
