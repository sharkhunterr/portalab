import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import type { FieldDef } from "./api";

/** Inputs for a ticket type's or feedback form's custom fields (spec 016 R4); required fields are marked. */
export function FieldInputs({
  defs,
  values,
  onChange,
  errors = [],
}: {
  defs: FieldDef[];
  values: Record<string, unknown>;
  onChange: (values: Record<string, unknown>) => void;
  errors?: string[];
}) {
  const set = (key: string, value: unknown) => onChange({ ...values, [key]: value });
  return (
    <>
      {defs.map((def) => {
        const label = def.required ? `${def.label} *` : def.label;
        const error = errors.includes(def.key) ? "⚠" : undefined;
        if (def.type === "select")
          return (
            <SelectField
              key={def.key}
              label={label}
              value={String(values[def.key] ?? "")}
              onChange={(e) => set(def.key, e.target.value)}
              error={error}
            >
              <option value="">—</option>
              {(def.options ?? []).map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </SelectField>
          );
        if (def.type === "boolean")
          return (
            <CheckboxField
              key={def.key}
              label={label}
              checked={Boolean(values[def.key])}
              onChange={(e) => set(def.key, e.target.checked)}
            />
          );
        if (def.type === "long_text")
          return (
            <div className="ds-field" key={def.key}>
              <label htmlFor={`field-${def.key}`}>{label}</label>
              <textarea
                id={`field-${def.key}`}
                rows={4}
                value={String(values[def.key] ?? "")}
                onChange={(e) => set(def.key, e.target.value)}
                aria-invalid={error ? true : undefined}
              />
            </div>
          );
        return (
          <TextField
            key={def.key}
            label={label}
            type={def.type === "number" ? "number" : def.type === "date" ? "date" : "text"}
            value={String(values[def.key] ?? "")}
            onChange={(e) => set(def.key, def.type === "number" ? Number(e.target.value) : e.target.value)}
            error={error}
          />
        );
      })}
    </>
  );
}
