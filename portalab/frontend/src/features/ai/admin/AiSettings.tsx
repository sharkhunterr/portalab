import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextAreaField, TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { type AiConfig, type AiConfigUpdate, useAiAdmin, useAiConfig } from "../api";
import { IDEAS } from "../panel/AiPanel";
import { ModelServer } from "./ModelServer";
import { ToolChoice } from "./ToolChoice";

/**
 * Assistant settings (spec 018 T031, ``ai.manage``; issue 176: one page each in the assistant's hub) — its
 * model (server, credential, limits, test), its identity and instructions, its tools. Each page saves only
 * what it shows. The provider credential is write-only (only "a credential is stored" is shown).
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

/** A settings page's form: the stored values, edited, and saved — only the fields the page shows. */
function SettingsForm({
  title,
  icon,
  description,
  build,
  children,
  extra,
}: {
  title: string;
  icon: string;
  description?: string;
  build: (values: Values) => AiConfigUpdate;
  children: (values: Values, set: (next: Values) => void, data: AiConfig) => ReactNode;
  extra?: ReactNode;
}) {
  const t = useT();
  const config = useAiConfig();
  const { save } = useAiAdmin();
  const [values, setValues] = useState<Values>({});
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (config.data) setValues({ ...(config.data.values as Values) });
  }, [config.data]);
  if (!config.data) return null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(build(values), { onSuccess: () => setSaved(true) });
  };
  const set = (next: Values) => {
    setSaved(false);
    setValues(next);
  };
  return (
    <AdminSection title={title} icon={icon} description={description}>
      <form className="ds-stack" onSubmit={submit}>
        {children(values, set, config.data)}
        <div className="ds-stack--row">
          <Button type="submit" disabled={save.isPending}>
            {t("ai:admin.save")}
          </Button>
          {extra}
        </div>
        {saved ? <p role="status">{t("ai:admin.saved")}</p> : null}
      </form>
    </AdminSection>
  );
}

/** The model: on or off, its server and model, its credential, its limits — and a test. */
export function ModelSettings() {
  const t = useT();
  const { test } = useAiAdmin();
  const [access, setAccess] = useState("");
  return (
    <>
      <SettingsForm
        title={t("ai:admin.page.model")}
        icon="brain"
        build={(values) => {
          const body: AiConfigUpdate = {
            enabled: Boolean(values.enabled),
            provider_endpoint: String(values.provider_endpoint ?? ""),
            provider_model: String(values.provider_model ?? ""),
            provider_reasoning: String(values.provider_reasoning ?? "") as
              | ""
              | "none"
              | "low"
              | "medium"
              | "high",
            ...Object.fromEntries(NUMBERS.map(([key]) => [key, Number(values[key])])),
            ...(access ? { provider_secret: access } : {}),
          };
          setAccess("");
          return body;
        }}
        extra={
          <Button type="button" variant="secondary" onClick={() => test.mutate()} disabled={test.isPending}>
            {t("ai:admin.test")}
          </Button>
        }
      >
        {(values, set, data) => (
          <>
            <CheckboxField
              label={t("ai:admin.enabled")}
              checked={Boolean(values.enabled)}
              onChange={(event) => set({ ...values, enabled: event.target.checked })}
            />
            <ModelServer values={values} onChange={set} />
            <TextField
              label={t("ai:admin.access")}
              type="password"
              autoComplete="off"
              value={access}
              hint={
                data.provider_secret_set
                  ? `${t("ai:admin.accessSet")} ${t("ai:admin.accessHint")}`
                  : undefined
              }
              onChange={(event) => setAccess(event.target.value)}
            />
            <fieldset className="ai-limits">
              <legend>{t("ai:admin.limits")}</legend>
              {NUMBERS.map(([key, label]) => (
                <TextField
                  key={key}
                  label={t(label)}
                  type="number"
                  min={0}
                  value={String(values[key] ?? "")}
                  onChange={(event) => set({ ...values, [key]: event.target.value })}
                />
              ))}
            </fieldset>
          </>
        )}
      </SettingsForm>
      {test.data ? (
        <p role="status">
          {test.data.ok
            ? t("ai:admin.testOk", { ms: test.data.latency_ms })
            : t("ai:admin.testFailed", { code: test.data.code ?? "" })}
        </p>
      ) : null}
    </>
  );
}

/** Its identity and instructions: its name, its role, what it does when it does not know, its first ideas. */
export function IdentitySettings() {
  const t = useT();
  return (
    <SettingsForm
      title={t("ai:admin.persona.title")}
      icon="sparkles"
      build={(values) => ({
        assistant_name: String(values.assistant_name ?? "").trim(),
        assistant_role: String(values.assistant_role ?? "").trim(),
        assistant_fallback: String(values.assistant_fallback ?? "").trim(),
        assistant_ideas: ideasOf(values.assistant_ideas),
        auto_navigate: Boolean(values.auto_navigate),
      })}
    >
      {(values, set) => (
        <>
          <TextField
            label={t("ai:admin.persona.name")}
            hint={t("ai:admin.persona.nameHint")}
            placeholder="Nova"
            maxLength={40}
            value={String(values.assistant_name ?? "")}
            onChange={(event) => set({ ...values, assistant_name: event.target.value })}
          />
          <TextAreaField
            label={t("ai:admin.persona.role")}
            hint={t("ai:admin.persona.roleHint")}
            rows={3}
            maxLength={800}
            value={String(values.assistant_role ?? "")}
            onChange={(event) => set({ ...values, assistant_role: event.target.value })}
          />
          <TextAreaField
            label={t("ai:admin.persona.fallback")}
            hint={t("ai:admin.persona.fallbackHint")}
            rows={3}
            maxLength={800}
            value={String(values.assistant_fallback ?? "")}
            onChange={(event) => set({ ...values, assistant_fallback: event.target.value })}
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
            onChange={(event) => set({ ...values, assistant_ideas: event.target.value })}
          />
          <CheckboxField
            label={t("ai:admin.autoNavigate")}
            checked={Boolean(values.auto_navigate)}
            onChange={(event) => set({ ...values, auto_navigate: event.target.checked })}
          />
        </>
      )}
    </SettingsForm>
  );
}

/** Its tools: which of the portal's it may use. */
export function ToolSettings() {
  const t = useT();
  const disabledOf = (values: Values) => new Set((values.tools_disabled as string[] | undefined) ?? []);
  return (
    <SettingsForm
      title={t("ai:admin.tools")}
      icon="wrench"
      build={(values) => ({ tools_disabled: [...disabledOf(values)] })}
    >
      {(values, set, data) => (
        <ToolChoice
          tools={data.tools}
          disabled={disabledOf(values)}
          onChange={(next) => set({ ...values, tools_disabled: [...next] })}
        />
      )}
    </SettingsForm>
  );
}
