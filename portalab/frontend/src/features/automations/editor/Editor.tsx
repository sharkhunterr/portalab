import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { type Catalog, type Definition, useAutomationAdmin, useCatalog } from "../api";
import { ACTION_ICONS, actionLabel, conditionLabel, eventLabel, paramLabel, TRIGGER_ICONS } from "../labels";
import {
  type Draft,
  emptyDraft,
  type FilterDraft,
  fromDraft,
  hintOf,
  keyOf,
  type LeafDraft,
  type StepDraft,
  stepId,
  toDraft,
} from "./draft";

/**
 * The automation builder (027 redesign): three lanes read top to bottom — WHEN (an event with its filters,
 * a delay after an event, a schedule or a moment), IF (conditions, all or any of them), THEN (steps in
 * order, each with a field per declared parameter). The event's fields are offered as variables
 * (« ${event.service_label} ») that a click puts into the field being edited. The server validates; its
 * problems are listed. Creates a draft, or saves a new version of an existing automation.
 */
export function Editor({
  initial,
  automationId,
  initialKey,
}: {
  initial?: Definition | undefined;
  automationId?: string | undefined;
  initialKey?: string | undefined;
}) {
  const t = useT();
  const navigate = useNavigate();
  const catalog = useCatalog().data;
  const admin = useAutomationAdmin();
  const [draft, setDraft] = useState<Draft>(() => (initial ? toDraft(initial) : emptyDraft()));
  const [key, setKey] = useState(initialKey ?? "");
  const [keyTouched, setKeyTouched] = useState(Boolean(initialKey));
  const [problems, setProblems] = useState<string[] | null>(null);
  const [advanced, setAdvanced] = useState(false);
  // where a variable goes when its chip is clicked: the field last focused
  const focus = useRef<((value: string) => void) | null>(null);
  useEffect(() => {
    if (initial) setDraft(toDraft(initial));
  }, [initial]);
  const patch = (next: Partial<Draft>) => setDraft((d) => ({ ...d, ...next }));
  const fields =
    draft.trigger.kind === "event" || draft.trigger.kind === "relative"
      ? (catalog?.triggers.event_fields?.[draft.trigger.event_type ?? ""] ?? [])
      : [];
  const saving = admin.create.isPending || admin.update.isPending;

  const save = () => {
    const { definition, problems: local } = fromDraft(draft, catalog);
    if (local.length) {
      setProblems(local.map((p) => t("automations:editor.invalidJson", { field: p })));
      return;
    }
    const failed = (error: unknown) =>
      setProblems(
        error instanceof ApiError
          ? ((error.extensions.errors as string[] | undefined) ?? [error.message])
          : [t("automations:editor.failed")],
      );
    if (automationId) {
      admin.update.mutate(
        { id: automationId, definition: definition as unknown as Record<string, unknown> },
        { onSuccess: () => navigate(`/admin/automations/${automationId}`), onError: failed },
      );
    } else {
      admin.create.mutate(
        { key: key || keyOf(draft.name), definition: definition as unknown as Record<string, unknown> },
        { onSuccess: (created) => navigate(`/admin/automations/${created.id}`), onError: failed },
      );
    }
  };

  return (
    <form
      className="automation-editor"
      onSubmit={(event) => {
        event.preventDefault();
        save();
      }}
    >
      <section className="automation-editor__identity ds-card">
        <TextField
          label={t("automations:name")}
          required
          value={draft.name}
          placeholder={t("automations:editor.namePlaceholder")}
          onChange={(e) => {
            patch({ name: e.target.value });
            if (!automationId && !keyTouched) setKey(keyOf(e.target.value));
          }}
        />
        {automationId ? null : (
          <TextField
            label={t("automations:identifier")}
            hint={t("automations:editor.keyHint")}
            value={key}
            pattern="[a-z][a-z0-9_]{1,63}"
            onChange={(e) => {
              setKey(e.target.value);
              setKeyTouched(true);
            }}
          />
        )}
      </section>

      <ol className="automation-flow automation-flow--edit">
        <li className="automation-flow__node" data-part="when">
          <span className="automation-flow__badge">
            <Icon name={TRIGGER_ICONS[draft.trigger.kind] ?? "zap"} size={16} />
            {t("automations:flow.when")}
          </span>
          <TriggerEditor draft={draft} catalog={catalog} onChange={patch} />
        </li>

        <li className="automation-flow__node" data-part="if">
          <span className="automation-flow__badge">
            <Icon name="list" size={16} />
            {t("automations:flow.if")}
            <span className="automation-flow__mode">{t("automations:editor.optional")}</span>
          </span>
          <ConditionsEditor draft={draft} catalog={catalog} onChange={patch} focus={focus} />
        </li>

        {draft.steps.map((step, index) => (
          <li key={step.id} className="automation-flow__node" data-part="then">
            <span className="automation-flow__badge">
              <Icon name={ACTION_ICONS[step.action] ?? "play"} size={16} />
              {index === 0 ? t("automations:flow.then") : t("automations:flow.next")}
              <span className="automation-flow__index">{index + 1}</span>
            </span>
            <StepEditor
              step={step}
              index={index}
              count={draft.steps.length}
              catalog={catalog}
              focus={focus}
              onChange={(next) =>
                patch({ steps: draft.steps.map((s, i) => (i === index ? { ...s, ...next } : s)) })
              }
              onMove={(delta) => {
                const steps = [...draft.steps];
                const [moved] = steps.splice(index, 1);
                if (moved) steps.splice(index + delta, 0, moved);
                patch({ steps });
              }}
              onRemove={() => patch({ steps: draft.steps.filter((_, i) => i !== index) })}
            />
          </li>
        ))}
        <li className="automation-flow__add">
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              patch({
                steps: [...draft.steps, { id: stepId(), action: "", params: {}, on_error: "stop" }],
              })
            }
          >
            <Icon name="plus" size={16} />
            {t("automations:steps.add")}
          </Button>
        </li>
      </ol>

      {fields.length ? (
        <aside className="automation-variables ds-card" aria-label={t("automations:editor.variables")}>
          <strong>
            <Icon name="code" size={16} /> {t("automations:editor.variables")}
          </strong>
          <p className="automation-meta">{t("automations:editor.variablesHint")}</p>
          <div className="automation-variables__chips">
            {fields.map((field) => (
              <button
                key={field}
                type="button"
                className="automation-chip"
                onClick={() => focus.current?.(`\${event.${field}}`)}
              >
                {`\${event.${field}}`}
              </button>
            ))}
          </div>
        </aside>
      ) : null}

      <details
        className="automation-advanced ds-card"
        open={advanced}
        onToggle={(e) => setAdvanced(e.currentTarget.open)}
      >
        <summary>
          <Icon name="settings" size={16} /> {t("automations:editor.limits")}
        </summary>
        <div className="automation-advanced__grid">
          <TextField
            label={t("automations:editor.cooldown")}
            hint={t("automations:editor.cooldownHint")}
            type="number"
            min={0}
            value={draft.cooldownMinutes}
            onChange={(e) => patch({ cooldownMinutes: e.target.value })}
          />
          <TextField
            label={t("automations:editor.dedupKey")}
            hint={t("automations:editor.dedupKeyHint")}
            value={draft.dedupKey}
            onChange={(e) => patch({ dedupKey: e.target.value })}
          />
          <TextField
            label={t("automations:editor.dedupWindow")}
            type="number"
            min={0}
            value={draft.dedupWindowMinutes}
            onChange={(e) => patch({ dedupWindowMinutes: e.target.value })}
          />
          <TextField
            label={t("automations:editor.rate")}
            type="number"
            min={1}
            value={draft.ratePerMin}
            onChange={(e) => patch({ ratePerMin: e.target.value })}
          />
        </div>
      </details>

      {problems?.length ? (
        <section className="automation-problems" role="alert" aria-label={t("automations:validation.title")}>
          <strong>
            <Icon name="alert" size={16} /> {t("automations:validation.title")}
          </strong>
          <ul>
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <div className="automation-editor__actions">
        <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
          {t("automations:editor.cancel")}
        </Button>
        <Button type="submit" disabled={!draft.name.trim() || saving}>
          <Icon name={saving ? "spinner" : "check"} size={16} />
          {automationId ? t("automations:editor.saveVersion") : t("automations:save")}
        </Button>
      </div>
    </form>
  );
}

function TriggerEditor({
  draft,
  catalog,
  onChange,
}: {
  draft: Draft;
  catalog: Catalog | undefined;
  onChange: (next: Partial<Draft>) => void;
}) {
  const t = useT();
  const trigger = draft.trigger;
  const set = (next: Partial<Draft["trigger"]>) => onChange({ trigger: { ...trigger, ...next } });
  const events = catalog?.triggers.events ?? [];
  const fields = catalog?.triggers.event_fields?.[trigger.event_type ?? ""] ?? [];
  const schedule = trigger.schedule ?? { frequency: "daily" as const, time: "09:00" };
  return (
    <div className="automation-lane">
      <fieldset className="automation-kinds">
        <legend className="visually-hidden">{t("automations:trigger.kind")}</legend>
        {(["event", "relative", "recurring", "at"] as const).map((kind) => (
          <label key={kind} className="automation-kind" data-checked={trigger.kind === kind || undefined}>
            <input
              type="radio"
              name="automation-trigger-kind"
              value={kind}
              checked={trigger.kind === kind}
              onChange={() =>
                set({
                  kind,
                  ...(kind === "recurring" && !trigger.schedule
                    ? { schedule: { frequency: "daily", time: "09:00" } }
                    : {}),
                })
              }
            />
            <Icon name={TRIGGER_ICONS[kind] ?? "zap"} size={18} />
            <strong>{t(`automations:kind.${kind}`)}</strong>
            <span>{t(`automations:kind.${kind}.hint`)}</span>
          </label>
        ))}
      </fieldset>
      {trigger.kind === "event" || trigger.kind === "relative" ? (
        <>
          <SelectField
            label={t("automations:trigger.eventType")}
            value={trigger.event_type ?? ""}
            onChange={(e) => set({ event_type: e.target.value })}
          >
            <option value="" />
            {groupEvents(events).map(([domain, names]) => (
              <optgroup key={domain} label={domain}>
                {names.map((name) => (
                  <option key={name} value={name}>
                    {eventLabel(t, name, catalog)}
                  </option>
                ))}
              </optgroup>
            ))}
          </SelectField>
          {trigger.event_type ? <code className="automation-meta">{trigger.event_type}</code> : null}
          {trigger.kind === "relative" ? (
            <div className="automation-row">
              <TextField
                label={t("automations:editor.offset")}
                hint={t("automations:editor.offsetHint")}
                type="number"
                value={String(trigger.offset_minutes ?? 0)}
                onChange={(e) => set({ offset_minutes: Number(e.target.value) })}
              />
              <SelectField
                label={t("automations:editor.reference")}
                value={trigger.reference ?? ""}
                onChange={(e) => set({ reference: e.target.value })}
              >
                <option value="" />
                {fields.map((f) => (
                  <option key={f} value={f}>
                    {paramLabel(t, f)}
                  </option>
                ))}
              </SelectField>
            </div>
          ) : null}
          <FiltersEditor
            filters={draft.filters}
            fields={fields}
            onChange={(filters) => onChange({ filters })}
          />
        </>
      ) : null}
      {trigger.kind === "recurring" ? (
        <div className="automation-row">
          <SelectField
            label={t("automations:editor.frequency")}
            value={schedule.frequency}
            onChange={(e) =>
              set({ schedule: { ...schedule, frequency: e.target.value as typeof schedule.frequency } })
            }
          >
            {(["daily", "weekly", "monthly"] as const).map((f) => (
              <option key={f} value={f}>
                {t(`automations:frequency.${f}`)}
              </option>
            ))}
          </SelectField>
          {schedule.frequency === "weekly" ? (
            <SelectField
              label={t("automations:editor.weekday")}
              value={String(schedule.weekday ?? 0)}
              onChange={(e) => set({ schedule: { ...schedule, weekday: Number(e.target.value) } })}
            >
              {[0, 1, 2, 3, 4, 5, 6].map((d) => (
                <option key={d} value={d}>
                  {t(`automations:weekday.${d}`)}
                </option>
              ))}
            </SelectField>
          ) : null}
          {schedule.frequency === "monthly" ? (
            <TextField
              label={t("automations:editor.monthDay")}
              type="number"
              min={1}
              max={28}
              value={String(schedule.day ?? 1)}
              onChange={(e) => set({ schedule: { ...schedule, day: Number(e.target.value) } })}
            />
          ) : null}
          <TextField
            label={t("automations:editor.time")}
            type="time"
            value={schedule.time}
            onChange={(e) => set({ schedule: { ...schedule, time: e.target.value } })}
          />
          <TextField
            label={t("automations:editor.timezone")}
            value={trigger.timezone ?? "UTC"}
            onChange={(e) => set({ timezone: e.target.value })}
          />
        </div>
      ) : null}
      {trigger.kind === "at" ? (
        <TextField
          label={t("automations:trigger.at")}
          type="datetime-local"
          value={trigger.at ? trigger.at.slice(0, 16) : ""}
          onChange={(e) => set({ at: e.target.value ? new Date(e.target.value).toISOString() : null })}
        />
      ) : null}
    </div>
  );
}

function groupEvents(events: string[]): Array<[string, string[]]> {
  const groups = new Map<string, string[]>();
  for (const name of events) {
    const domain = name.split(".")[0] ?? name;
    groups.set(domain, [...(groups.get(domain) ?? []), name]);
  }
  return [...groups.entries()];
}

const OPS: FilterDraft["op"][] = ["eq", "ne", "in", "gt", "gte", "lt", "lte", "contains"];

function FiltersEditor({
  filters,
  fields,
  onChange,
}: {
  filters: FilterDraft[];
  fields: string[];
  onChange: (filters: FilterDraft[]) => void;
}) {
  const t = useT();
  return (
    <fieldset className="automation-sub">
      <legend>{t("automations:editor.filters")}</legend>
      {filters.map((filter, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: filters are positional
        <div key={index} className="automation-row automation-row--tight">
          <SelectField
            label={t("automations:editor.field")}
            value={filter.field}
            onChange={(e) =>
              onChange(filters.map((f, i) => (i === index ? { ...f, field: e.target.value } : f)))
            }
          >
            <option value="" />
            {[...new Set([...fields, filter.field].filter(Boolean))].map((f) => (
              <option key={f} value={f}>
                {paramLabel(t, f)}
              </option>
            ))}
          </SelectField>
          <SelectField
            label={t("automations:editor.op")}
            value={filter.op}
            onChange={(e) =>
              onChange(
                filters.map((f, i) => (i === index ? { ...f, op: e.target.value as FilterDraft["op"] } : f)),
              )
            }
          >
            {OPS.map((op) => (
              <option key={op} value={op}>
                {t(`automations:op.${op}`)}
              </option>
            ))}
          </SelectField>
          <TextField
            label={t("automations:editor.value")}
            hint={filter.op === "in" ? t("automations:editor.listHint") : undefined}
            value={filter.value}
            onChange={(e) =>
              onChange(filters.map((f, i) => (i === index ? { ...f, value: e.target.value } : f)))
            }
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t("automations:editor.removeFilter")}
            onClick={() => onChange(filters.filter((_, i) => i !== index))}
          >
            <Icon name="close" size={16} />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="ghost"
        onClick={() => onChange([...filters, { field: "", op: "eq", value: "" }])}
      >
        <Icon name="plus" size={16} />
        {t("automations:editor.addFilter")}
      </Button>
    </fieldset>
  );
}

function ParamField({
  name,
  hint,
  value,
  required,
  focus,
  onChange,
}: {
  name: string;
  hint: string | undefined;
  value: string;
  required: boolean;
  focus: React.MutableRefObject<((value: string) => void) | null>;
  onChange: (value: string) => void;
}) {
  const t = useT();
  const type = hintOf(hint);
  const label = paramLabel(t, name) + (required ? " *" : "");
  const remember = () => {
    focus.current = (inserted) => onChange(`${value}${inserted}`);
  };
  if (type.choices) {
    return (
      <SelectField label={label} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="" />
        {type.choices.map((c) => (
          <option key={c} value={c}>
            {maybeChoice(t, name, c)}
          </option>
        ))}
      </SelectField>
    );
  }
  if (type.item === "boolean") {
    return (
      <CheckboxField
        label={label}
        checked={value === "true"}
        onChange={(e) => onChange(String(e.target.checked))}
      />
    );
  }
  if (type.object) {
    return (
      <div className="ds-field">
        <label htmlFor={`param-${name}`}>{label}</label>
        <textarea
          id={`param-${name}`}
          rows={3}
          spellCheck={false}
          className="automation-json"
          value={value}
          placeholder={hint}
          onFocus={remember}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    );
  }
  return (
    <TextField
      label={label}
      hint={type.list ? t("automations:editor.listHint") : undefined}
      type={type.item === "integer" && !type.list ? "number" : type.item === "HH:MM" ? "time" : "text"}
      value={value}
      onFocus={remember}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

function maybeChoice(t: ReturnType<typeof useT>, name: string, choice: string): string {
  const key = `automations:choice.${name}.${choice}`;
  const text = t(key);
  return text === key.split(":").slice(1).join(":") ? choice : text;
}

function ConditionsEditor({
  draft,
  catalog,
  onChange,
  focus,
}: {
  draft: Draft;
  catalog: Catalog | undefined;
  onChange: (next: Partial<Draft>) => void;
  focus: React.MutableRefObject<((value: string) => void) | null>;
}) {
  const t = useT();
  if (draft.rawConditions !== null) {
    return (
      <div className="ds-field">
        <label htmlFor="automation-raw-conditions">{t("automations:editor.rawConditions")}</label>
        <textarea
          id="automation-raw-conditions"
          rows={6}
          className="automation-json"
          spellCheck={false}
          value={draft.rawConditions}
          onChange={(e) => onChange({ rawConditions: e.target.value })}
        />
      </div>
    );
  }
  const update = (index: number, next: Partial<LeafDraft>) =>
    onChange({ leaves: draft.leaves.map((l, i) => (i === index ? { ...l, ...next } : l)) });
  return (
    <div className="automation-lane">
      {draft.leaves.length > 1 ? (
        <SelectField
          label={t("automations:editor.combine")}
          value={draft.mode}
          onChange={(e) => onChange({ mode: e.target.value as "all" | "any" })}
        >
          <option value="all">{t("automations:flow.mode.all")}</option>
          <option value="any">{t("automations:flow.mode.any")}</option>
        </SelectField>
      ) : null}
      {draft.leaves.length === 0 ? (
        <p className="automation-meta">{t("automations:editor.noConditions")}</p>
      ) : null}
      {draft.leaves.map((leaf, index) => {
        const declared = catalog?.conditions.find((c) => c.key === leaf.leaf);
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: conditions are positional
          <div key={index} className="automation-sub">
            <div className="automation-row automation-row--tight">
              <SelectField
                label={t("automations:editor.condition")}
                value={leaf.leaf}
                onChange={(e) => update(index, { leaf: e.target.value, params: {} })}
              >
                <option value="" />
                {(catalog?.conditions ?? []).map((c) => (
                  <option key={c.key} value={c.key}>
                    {conditionLabel(t, c.key, catalog)}
                  </option>
                ))}
              </SelectField>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("automations:editor.removeCondition")}
                onClick={() => onChange({ leaves: draft.leaves.filter((_, i) => i !== index) })}
              >
                <Icon name="close" size={16} />
              </Button>
            </div>
            <div className="automation-params">
              {Object.entries(declared?.params ?? {}).map(([name, hint]) => (
                <ParamField
                  key={name}
                  name={name}
                  hint={hint}
                  required={!hintOf(hint).optional}
                  value={leaf.params[name] ?? ""}
                  focus={focus}
                  onChange={(value) => update(index, { params: { ...leaf.params, [name]: value } })}
                />
              ))}
            </div>
          </div>
        );
      })}
      <Button
        type="button"
        variant="ghost"
        onClick={() => onChange({ leaves: [...draft.leaves, { leaf: "", params: {} }] })}
      >
        <Icon name="plus" size={16} />
        {t("automations:editor.addCondition")}
      </Button>
    </div>
  );
}

function StepEditor({
  step,
  index,
  count,
  catalog,
  focus,
  onChange,
  onMove,
  onRemove,
}: {
  step: StepDraft;
  index: number;
  count: number;
  catalog: Catalog | undefined;
  focus: React.MutableRefObject<((value: string) => void) | null>;
  onChange: (next: Partial<StepDraft>) => void;
  onMove: (delta: number) => void;
  onRemove: () => void;
}) {
  const t = useT();
  const action = catalog?.actions.find((a) => a.key === step.action);
  const declared = Object.entries(action?.params ?? {});
  const extra = Object.keys(step.params).filter((name) => !action?.params?.[name]);
  return (
    <div className="automation-lane">
      <div className="automation-row automation-row--tight">
        <SelectField
          label={t("automations:steps.action")}
          value={step.action}
          onChange={(e) => onChange({ action: e.target.value, params: {} })}
        >
          <option value="" />
          {(catalog?.actions ?? []).map((a) => (
            <option key={a.key} value={a.key}>
              {actionLabel(t, a.key, catalog)}
              {a.sensitivity !== "normal" ? ` — ${t(`automations:sensitivity.${a.sensitivity}`)}` : ""}
            </option>
          ))}
        </SelectField>
        <div className="automation-step-tools">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t("automations:editor.up")}
            disabled={index === 0}
            onClick={() => onMove(-1)}
          >
            <Icon name="arrow-up" size={16} />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t("automations:editor.down")}
            disabled={index === count - 1}
            onClick={() => onMove(1)}
          >
            <Icon name="arrow-down" size={16} />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t("automations:steps.remove")}
            disabled={count === 1}
            onClick={onRemove}
          >
            <Icon name="trash" size={16} />
          </Button>
        </div>
      </div>
      {action?.sensitivity && action.sensitivity !== "normal" ? (
        <p className="automation-meta">
          <Icon name="shield" size={14} /> {t("automations:editor.sensitive")}
        </p>
      ) : null}
      {declared.length || extra.length ? (
        <div className="automation-params">
          {declared.map(([name, hint]) => (
            <ParamField
              key={name}
              name={name}
              hint={hint}
              required={action?.required.includes(name) ?? false}
              value={step.params[name] ?? ""}
              focus={focus}
              onChange={(value) => onChange({ params: { ...step.params, [name]: value } })}
            />
          ))}
          {extra.map((name) => (
            <ParamField
              key={name}
              name={name}
              hint="any"
              required={false}
              value={step.params[name] ?? ""}
              focus={focus}
              onChange={(value) => onChange({ params: { ...step.params, [name]: value } })}
            />
          ))}
        </div>
      ) : null}
      <CheckboxField
        label={t("automations:editor.continueOnError")}
        checked={step.on_error === "continue"}
        onChange={(e) => onChange({ on_error: e.target.checked ? "continue" : "stop" })}
      />
    </div>
  );
}
