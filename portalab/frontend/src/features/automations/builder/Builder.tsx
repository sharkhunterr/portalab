import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Catalog, useAutomationAdmin, useCatalog } from "../api";

interface StepDraft {
  id: string;
  action: string;
  params: string;
  on_error: "stop" | "continue";
}

let counter = 0;
const nextId = () => `step_${++counter}`;

/**
 * Automation builder (spec 019 T030): WHEN (trigger picker from the catalog) → IF (closed condition tree)
 * → THEN (ordered steps from the action catalog, with their declared parameters). The server validates
 * everything; its problems are listed in the validation panel. Keyboard accessible (plain form controls).
 */
export function Builder({ onCreated }: { onCreated?: (id: string) => void }) {
  const t = useT();
  const catalog = useCatalog();
  const admin = useAutomationAdmin();
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"event" | "recurring">("event");
  const [eventType, setEventType] = useState("");
  const [time, setTime] = useState("09:00");
  const [conditions, setConditions] = useState("");
  const [steps, setSteps] = useState<StepDraft[]>([
    { id: nextId(), action: "", params: "{}", on_error: "stop" },
  ]);
  const [problems, setProblems] = useState<string[] | null>(null);
  const data: Catalog | undefined = catalog.data;
  const build = (): Record<string, unknown> | null => {
    try {
      return {
        name,
        trigger:
          kind === "event"
            ? { kind: "event", event_type: eventType }
            : { kind: "recurring", schedule: { frequency: "daily", time }, timezone: "UTC" },
        ...(conditions.trim() ? { conditions: JSON.parse(conditions) } : {}),
        steps: steps.map((s) => ({
          id: s.id,
          action: s.action,
          params: JSON.parse(s.params || "{}"),
          on_error: s.on_error,
        })),
      };
    } catch {
      return null;
    }
  };
  const save = () => {
    const definition = build();
    if (!definition) {
      setProblems(["JSON"]);
      return;
    }
    admin.create.mutate(
      { key, definition },
      {
        onSuccess: (automation) => {
          setProblems([]);
          onCreated?.(automation.id);
        },
        onError: (error) =>
          setProblems(
            error instanceof ApiError
              ? ((error.extensions.errors as string[] | undefined) ?? [error.message])
              : ["?"],
          ),
      },
    );
  };
  const update = (index: number, patch: Partial<StepDraft>) =>
    setSteps(steps.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  return (
    <section aria-labelledby="automation-builder" className="ds-stack automation-builder">
      <h2 id="automation-builder">{t("automations:new")}</h2>
      <TextField label={t("automations:identifier")} value={key} onChange={(e) => setKey(e.target.value)} />
      <TextField label={t("automations:name")} value={name} onChange={(e) => setName(e.target.value)} />
      <fieldset className="ds-stack">
        <legend>{t("automations:trigger.title")}</legend>
        <SelectField
          label={t("automations:trigger.kind")}
          value={kind}
          onChange={(e) => setKind(e.target.value as "event" | "recurring")}
        >
          <option value="event">{t("automations:trigger.event")}</option>
          <option value="recurring">{t("automations:trigger.recurring")}</option>
        </SelectField>
        {kind === "event" ? (
          <SelectField
            label={t("automations:trigger.eventType")}
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
          >
            <option value="" />
            {(data?.triggers.events ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </SelectField>
        ) : (
          <TextField
            label={t("automations:trigger.recurring")}
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        )}
      </fieldset>
      <label htmlFor="automation-conditions">{t("automations:conditions.title")}</label>
      <textarea
        id="automation-conditions"
        rows={4}
        value={conditions}
        placeholder={(data?.conditions ?? []).map((c) => c.key).join(", ")}
        onChange={(e) => setConditions(e.target.value)}
      />
      <fieldset className="ds-stack">
        <legend>{t("automations:steps.title")}</legend>
        <ol className="ds-stack">
          {steps.map((step, index) => {
            const action = data?.actions.find((a) => a.key === step.action);
            return (
              <li key={step.id} className="ds-card ds-stack">
                <SelectField
                  label={t("automations:steps.action")}
                  value={step.action}
                  onChange={(e) => update(index, { action: e.target.value })}
                >
                  <option value="" />
                  {(data?.actions ?? []).map((a) => (
                    <option key={a.key} value={a.key}>
                      {a.key} — {a.sensitivity}
                    </option>
                  ))}
                </SelectField>
                {action ? (
                  <p className="automation-meta">
                    {Object.entries(action.params)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ")}
                  </p>
                ) : null}
                <label htmlFor={`${step.id}-params`}>{t("automations:steps.params")}</label>
                <textarea
                  id={`${step.id}-params`}
                  rows={3}
                  value={step.params}
                  onChange={(e) => update(index, { params: e.target.value })}
                />
                <SelectField
                  label={t("automations:steps.onError")}
                  value={step.on_error}
                  onChange={(e) => update(index, { on_error: e.target.value as "stop" | "continue" })}
                >
                  <option value="stop">stop</option>
                  <option value="continue">continue</option>
                </SelectField>
                <Button variant="secondary" onClick={() => setSteps(steps.filter((_, i) => i !== index))}>
                  {t("automations:steps.remove")}
                </Button>
              </li>
            );
          })}
        </ol>
        <Button
          variant="secondary"
          onClick={() => setSteps([...steps, { id: nextId(), action: "", params: "{}", on_error: "stop" }])}
        >
          {t("automations:steps.add")}
        </Button>
      </fieldset>
      <Button onClick={save} disabled={!key || !name || admin.create.isPending}>
        {t("automations:save")}
      </Button>
      {problems ? (
        <section aria-live="polite" aria-label={t("automations:validation.title")}>
          {problems.length === 0 ? (
            <p role="status">{t("automations:validation.ok")}</p>
          ) : (
            <ul role="alert">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </section>
  );
}
