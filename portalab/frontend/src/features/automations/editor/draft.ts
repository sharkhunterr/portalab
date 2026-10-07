import type { Catalog, Definition, Filter, Trigger } from "../api";
import { flatConditions, paramValue } from "../labels";

/**
 * The builder's working copy of a definition (027): every parameter is edited as text and converted back
 * with the type the catalog declares (list → comma-separated, integer → number, object → JSON), so an
 * administrator never writes JSON for an ordinary rule.
 */
export interface LeafDraft {
  leaf: string;
  params: Record<string, string>;
}
export interface StepDraft {
  id: string;
  action: string;
  params: Record<string, string>;
  on_error: "stop" | "continue";
}
export interface FilterDraft {
  field: string;
  op: Filter["op"];
  value: string;
}
export interface Draft {
  name: string;
  trigger: Trigger;
  filters: FilterDraft[];
  mode: "all" | "any";
  leaves: LeafDraft[];
  /** a condition tree deeper than one level, kept as JSON */
  rawConditions: string | null;
  steps: StepDraft[];
  cooldownMinutes: string;
  dedupKey: string;
  dedupWindowMinutes: string;
  ratePerMin: string;
  identity: Definition["identity"];
}

let counter = 0;
export const stepId = () => `step_${Date.now().toString(36)}_${++counter}`;

export function emptyDraft(): Draft {
  return {
    name: "",
    trigger: { kind: "event", event_type: "" },
    filters: [],
    mode: "all",
    leaves: [],
    rawConditions: null,
    steps: [{ id: stepId(), action: "", params: {}, on_error: "stop" }],
    cooldownMinutes: "",
    dedupKey: "",
    dedupWindowMinutes: "",
    ratePerMin: "",
    identity: undefined,
  };
}

const asText = (params: Record<string, unknown> | undefined) =>
  Object.fromEntries(Object.entries(params ?? {}).map(([k, v]) => [k, paramValue(v)]));

export function toDraft(definition: Definition): Draft {
  const flat = flatConditions(definition.conditions);
  const limits = definition.limits ?? {};
  const minutes = (seconds?: number | null) => (seconds ? String(Math.round(seconds / 60)) : "");
  return {
    name: definition.name,
    trigger: { ...definition.trigger },
    filters: (definition.trigger.filter ?? []).map((f) => ({
      field: f.field,
      op: f.op,
      value: paramValue(f.value),
    })),
    mode: flat?.mode ?? "all",
    leaves: (flat?.leaves ?? []).map((l) => ({ leaf: l.leaf, params: asText(l.params) })),
    rawConditions: flat === null ? JSON.stringify(definition.conditions, null, 2) : null,
    steps: definition.steps.map((s) => ({
      id: s.id,
      action: s.action,
      params: asText(s.params),
      on_error: s.on_error ?? "stop",
    })),
    cooldownMinutes: minutes(limits.cooldown_s),
    dedupKey: limits.dedup_key ?? "",
    dedupWindowMinutes: minutes(limits.dedup_window_s),
    ratePerMin: limits.rate_per_min ? String(limits.rate_per_min) : "",
    identity: definition.identity,
  };
}

/** A declared type: ``list[uuid]?`` → { list: true, item: "uuid", optional: true }; ``a|b`` → choices. */
export function hintOf(hint: string | undefined) {
  const raw = (hint ?? "string").trim();
  const optional = raw.endsWith("?") || raw.includes("? ");
  const base = raw
    .replace(/\?.*$/, "")
    .replace(/\s*\(.*\)$/, "")
    .trim();
  const list = base.startsWith("list[");
  const item = list ? base.slice(5, -1) : base;
  const choices = !list && item.includes("|") && !item.includes(" ") ? item.split("|") : null;
  return { optional, list, item, choices, object: item.startsWith("object") };
}

function scalar(text: string, item: string): unknown {
  if (item === "integer") {
    const n = Number(text);
    return Number.isFinite(n) ? n : text;
  }
  if (item === "any") {
    const n = Number(text);
    return text.trim() !== "" && Number.isFinite(n) ? n : text;
  }
  return text;
}

/** Text back to typed values; ``null`` when a JSON object does not parse (the field is flagged). */
export function typedParams(
  params: Record<string, string>,
  schema: Record<string, string> | undefined,
): { values: Record<string, unknown>; invalid: string[] } {
  const values: Record<string, unknown> = {};
  const invalid: string[] = [];
  for (const [name, text] of Object.entries(params)) {
    const hint = hintOf(schema?.[name]);
    if (text.trim() === "") continue; // an empty field is left out
    if (hint.object) {
      try {
        values[name] = JSON.parse(text);
      } catch {
        invalid.push(name);
      }
    } else if (hint.list) {
      values[name] = text
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean)
        .map((v) => scalar(v, hint.item));
    } else {
      values[name] = scalar(text, hint.item);
    }
  }
  return { values, invalid };
}

export function fromDraft(draft: Draft, catalog?: Catalog): { definition: Definition; problems: string[] } {
  const problems: string[] = [];
  const trigger: Trigger = { kind: draft.trigger.kind, timezone: draft.trigger.timezone ?? "UTC" };
  if (draft.trigger.kind === "event" || draft.trigger.kind === "relative") {
    trigger.event_type = draft.trigger.event_type ?? "";
    trigger.filter = draft.filters
      .filter((f) => f.field)
      .map((f) => ({
        field: f.field,
        op: f.op,
        value:
          f.op === "in"
            ? f.value
                .split(",")
                .map((v) => scalar(v.trim(), "any"))
                .filter((v) => v !== "")
            : scalar(f.value, "any"),
      }));
  }
  if (draft.trigger.kind === "relative") {
    trigger.reference = draft.trigger.reference ?? "";
    trigger.offset_minutes = Number(draft.trigger.offset_minutes ?? 0);
  }
  if (draft.trigger.kind === "at") trigger.at = draft.trigger.at ?? null;
  if (draft.trigger.kind === "recurring") trigger.schedule = draft.trigger.schedule ?? null;
  let conditions: Definition["conditions"] = null;
  if (draft.rawConditions !== null) {
    try {
      conditions = JSON.parse(draft.rawConditions);
    } catch {
      problems.push("conditions");
    }
  } else if (draft.leaves.length) {
    const nodes = draft.leaves
      .filter((l) => l.leaf)
      .map((l) => {
        const schema = catalog?.conditions.find((c) => c.key === l.leaf)?.params;
        const { values, invalid } = typedParams(l.params, schema);
        problems.push(...invalid.map((name) => `${l.leaf}.${name}`));
        return { leaf: l.leaf, params: values };
      });
    conditions = nodes.length === 1 ? nodes[0] : draft.mode === "any" ? { any_of: nodes } : { all_of: nodes };
  }
  const steps = draft.steps.map((s) => {
    const schema = catalog?.actions.find((a) => a.key === s.action)?.params;
    const { values, invalid } = typedParams(s.params, schema);
    problems.push(...invalid.map((name) => `${s.id}.${name}`));
    return { id: s.id, action: s.action, params: values, on_error: s.on_error };
  });
  const seconds = (minutes: string) => (minutes.trim() ? Math.max(0, Number(minutes)) * 60 : 0);
  const limits: NonNullable<Definition["limits"]> = {
    cooldown_s: seconds(draft.cooldownMinutes),
    dedup_window_s: seconds(draft.dedupWindowMinutes),
    ...(draft.dedupKey.trim() ? { dedup_key: draft.dedupKey.trim() } : {}),
    ...(draft.ratePerMin.trim() ? { rate_per_min: Number(draft.ratePerMin) } : {}),
  };
  return {
    definition: {
      name: draft.name.trim(),
      trigger,
      ...(conditions ? { conditions } : {}),
      steps,
      limits,
      ...(draft.identity ? { identity: draft.identity } : {}),
    },
    problems,
  };
}

/** A key from a name: « Incident si Plex tombe » → « incident_si_plex_tombe ». */
export function keyOf(name: string): string {
  return (
    name
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 60) || "automation"
  );
}
