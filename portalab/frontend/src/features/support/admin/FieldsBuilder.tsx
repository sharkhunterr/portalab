import { Button } from "../../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import type { FieldDef } from "../tickets/api";

/**
 * Form builder (027): the questions of a feedback form or the fields of a ticket type, as rows — a label,
 * a kind (short or long text, choice, several choices, rating, yes/no, number, date), required or not,
 * the choices of a choice — reordered with arrows. Keys are derived from labels and never shown.
 */
const TYPES: FieldDef["type"][] = [
  "text",
  "long_text",
  "select",
  "multi_select",
  "rating",
  "boolean",
  "number",
  "date",
];

function keyOf(label: string, taken: string[]): string {
  const base =
    label
      .normalize("NFKD")
      .replace(/[^\w\s]/g, "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_")
      .replace(/^[^a-z]+/, "")
      .slice(0, 32) || "field";
  let key = base;
  let n = 2;
  while (taken.includes(key)) key = `${base.slice(0, 36)}_${n++}`;
  return key;
}

export function FieldsBuilder({
  fields,
  onChange,
  staffOnly = false,
}: {
  fields: FieldDef[];
  onChange: (next: FieldDef[]) => void;
  /** Ticket types may hide a field from the requester. */
  staffOnly?: boolean;
}) {
  const t = useT();
  const patch = (index: number, next: Partial<FieldDef>) =>
    onChange(fields.map((f, i) => (i === index ? { ...f, ...next } : f)));
  const move = (index: number, by: number) => {
    const target = index + by;
    if (target < 0 || target >= fields.length) return;
    const next = [...fields];
    [next[index], next[target]] = [next[target] as FieldDef, next[index] as FieldDef];
    onChange(next);
  };
  return (
    <div className="fields-builder">
      {fields.length === 0 ? <p className="admin-muted">{t("support:builder.empty")}</p> : null}
      <ol className="fields-builder__list">
        {fields.map((field, index) => (
          <li key={field.key} className="fields-builder__row">
            <span className="fields-builder__index" aria-hidden="true">
              {index + 1}
            </span>
            <div className="fields-builder__main">
              <div className="fields-builder__line">
                <TextField
                  label={t("support:builder.label")}
                  required
                  maxLength={120}
                  value={field.label}
                  onChange={(e) => patch(index, { label: e.target.value })}
                />
                <SelectField
                  label={t("support:builder.type")}
                  value={field.type}
                  onChange={(e) => {
                    const type = e.target.value as FieldDef["type"];
                    const options =
                      type === "select" || type === "multi_select"
                        ? field.options?.length
                          ? field.options
                          : [t("support:builder.choiceA"), t("support:builder.choiceB")]
                        : [];
                    patch(index, { type, options });
                  }}
                >
                  {TYPES.map((type) => (
                    <option key={type} value={type}>
                      {t(`support:builder.types.${type}`)}
                    </option>
                  ))}
                </SelectField>
              </div>
              {field.type === "select" || field.type === "multi_select" ? (
                <TextField
                  label={t("support:builder.options")}
                  hint={t("support:builder.optionsHint")}
                  value={(field.options ?? []).join(", ")}
                  onChange={(e) =>
                    patch(index, {
                      options: e.target.value
                        .split(",")
                        .map((o) => o.trim())
                        .filter(Boolean),
                    })
                  }
                />
              ) : null}
              <div className="fields-builder__flags">
                <CheckboxField
                  label={t("support:builder.required")}
                  checked={field.required ?? false}
                  onChange={(e) => patch(index, { required: e.target.checked })}
                />
                {staffOnly ? (
                  <CheckboxField
                    label={t("support:builder.staffOnly")}
                    checked={field.visibility === "staff_only"}
                    onChange={(e) =>
                      patch(index, { visibility: e.target.checked ? "staff_only" : "requester_and_staff" })
                    }
                  />
                ) : null}
              </div>
            </div>
            <div className="fields-builder__tools">
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("support:builder.up")}
                disabled={index === 0}
                onClick={() => move(index, -1)}
              >
                <Icon name="arrow-up" size={16} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("support:builder.down")}
                disabled={index === fields.length - 1}
                onClick={() => move(index, 1)}
              >
                <Icon name="arrow-down" size={16} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("support:builder.remove")}
                onClick={() => onChange(fields.filter((_, i) => i !== index))}
              >
                <Icon name="trash" size={16} />
              </Button>
            </div>
          </li>
        ))}
      </ol>
      <Button
        variant="secondary"
        onClick={() => {
          const label = t("support:builder.newQuestion", { n: fields.length + 1 });
          onChange([
            ...fields,
            {
              key: keyOf(
                label,
                fields.map((f) => f.key),
              ),
              label,
              type: "text",
              required: false,
              options: [],
            },
          ]);
        }}
      >
        <Icon name="plus" size={16} />
        {t("support:builder.add")}
      </Button>
    </div>
  );
}
