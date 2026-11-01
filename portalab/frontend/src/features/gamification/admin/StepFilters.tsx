import { useId, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import type { Condition, EventTypeInfo } from "./tuning";

export const OPS: Condition["op"][] = ["eq", "ne", "in", "gt", "gte", "lt", "lte"];
// issue 160: the kinds a play may be — picked as chips for the playback actions, shown by their names
export const PLAY_KINDS: Array<[raw: string, source: string]> = [
  ["episode", "episode"],
  ["movie", "movie"],
  ["live", "live"],
  ["book", "book"],
  ["audiobook", "audiobook"],
  ["track", "music"],
  ["game", "game"],
];
export const playName = (t: (key: string) => string, raw: string) =>
  t(`gamification:sources.${PLAY_KINDS.find(([kind]) => kind === raw)?.[1] ?? "media"}`);

/** A condition's value as typed: a number for a numeric attribute, a list for « among ». */
export function parseValue(raw: string, numeric: boolean, op: Condition["op"]): Condition["value"] {
  const one = (text: string) =>
    numeric && text.trim() !== "" && !Number.isNaN(Number(text)) ? Number(text) : text.trim();
  if (op === "in")
    return raw
      .split(",")
      .map(one)
      .filter((v) => v !== "");
  return one(raw);
}

type Row = { field: string; op: Condition["op"]; value: string };

const toRows = (filter: Condition[] | undefined): Row[] =>
  (filter ?? []).map((c) => ({
    field: c.field,
    op: c.op,
    value: Array.isArray(c.value) ? c.value.join(", ") : String(c.value),
  }));

/**
 * issue 309: which of an action's events a step counts — « a film » (kind = movie), « the blind test »
 * (game = blindtest), « a quarter of an hour at least » (minutes ≥ 15), « the daily visit » (quest =
 * daily_visit). Each attribute of the action, an operator and a value; known values are suggested.
 */
export function StepFilters({
  filter,
  type,
  suggestions = {},
  onChange,
}: {
  filter: Condition[] | undefined;
  type: EventTypeInfo | undefined;
  /** Known values per attribute, with their names: the kinds of play, the games, the quests… */
  suggestions?: Record<string, Array<[value: string, name: string]>>;
  onChange: (next: Condition[]) => void;
}) {
  const t = useT();
  const id = useId();
  const [rows, setRows] = useState<Row[]>(() => toRows(filter));
  const fields = type?.fields ?? [];
  if (!fields.length) return null;
  const update = (next: Row[]) => {
    setRows(next);
    onChange(
      next
        .filter((row) => row.field && row.value.trim() !== "")
        .map((row) => ({
          field: row.field,
          op: row.op,
          value: parseValue(row.value, fields.find((f) => f.name === row.field)?.numeric ?? false, row.op),
        })),
    );
  };
  const set = (index: number, patch: Partial<Row>) =>
    update(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  return (
    <div className="gam-step-filters">
      {rows.length ? (
        <p className="gam-step-filters__title">{t("gamification:admin.quest.filters")}</p>
      ) : null}
      {rows.map((row, index) => {
        const known = suggestions[row.field] ?? [];
        const list = `${id}-${index}`;
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: rows have no identity of their own
          <div key={index} className="gam-condition">
            <SelectField
              label={t("gamification:admin.rule.field")}
              value={row.field}
              onChange={(e) => set(index, { field: e.target.value })}
            >
              {fields.map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name}
                </option>
              ))}
            </SelectField>
            <SelectField
              label={t("gamification:admin.rule.op")}
              value={row.op}
              onChange={(e) => set(index, { op: e.target.value as Condition["op"] })}
            >
              {OPS.map((op) => (
                <option key={op} value={op}>
                  {t(`gamification:admin.op.${op}`)}
                </option>
              ))}
            </SelectField>
            <TextField
              label={t("gamification:admin.rule.value")}
              hint={row.op === "in" ? t("gamification:admin.quest.amongHint") : undefined}
              list={known.length ? list : undefined}
              value={row.value}
              onChange={(e) => set(index, { value: e.target.value })}
            />
            {known.length ? (
              <datalist id={list}>
                {known.map(([value, name]) => (
                  <option key={value} value={value} label={name} />
                ))}
              </datalist>
            ) : null}
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("gamification:admin.remove")}
              onClick={() => update(rows.filter((_, i) => i !== index))}
            >
              <Icon name="trash" size={16} />
            </Button>
          </div>
        );
      })}
      <Button
        variant="ghost"
        onClick={() => setRows([...rows, { field: fields[0]?.name ?? "", op: "eq", value: "" }])}
      >
        <Icon name="plus" size={16} />
        {t("gamification:admin.rule.addCondition")}
      </Button>
    </div>
  );
}
