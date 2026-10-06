import { useId } from "react";
import { CheckboxField, SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { type Translate, useT } from "../../../i18n/hooks/useT";
import type { FieldDef } from "./api";

/** An option's words: the translated one for the built-in choices, else the option as written. */
export function optionLabel(t: Translate, option: string): string {
  const id = `support:option.${option}`;
  const label = t(id);
  return label === id.split(":")[1] ? option : label;
}

/** 1 to 5 stars (027): a radio group — arrows move, the value is read as « 4 out of 5 ». */
export function RatingInput({
  label,
  value,
  onChange,
  required,
}: {
  label: string;
  value: number | undefined;
  onChange: (value: number) => void;
  required?: boolean;
}) {
  const t = useT();
  const id = useId();
  return (
    <fieldset className="ds-field rating-input">
      <legend id={id}>
        {label}
        {required ? <span className="visually-hidden"> ({t("support:field.required")})</span> : null}
      </legend>
      <div className="rating-input__stars">
        {[1, 2, 3, 4, 5].map((star) => (
          <label key={star} className="rating-input__star" data-on={value !== undefined && star <= value}>
            <input
              type="radio"
              name={id}
              value={star}
              checked={value === star}
              onChange={() => onChange(star)}
              className="visually-hidden"
            />
            <Icon name="star" size={26} />
            <span className="visually-hidden">{t("support:rating.value", { value: star })}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Inputs for a ticket type's or feedback form's custom fields (spec 016 R4; 027 rating, multi-choice). */
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
  const t = useT();
  const set = (key: string, value: unknown) => onChange({ ...values, [key]: value });
  return (
    <>
      {defs.map((def) => {
        const label = def.required ? `${def.label} *` : def.label;
        const error = errors.includes(def.key) ? t("support:field.invalid") : undefined;
        if (def.type === "rating")
          return (
            <RatingInput
              key={def.key}
              label={label}
              required={def.required ?? false}
              value={typeof values[def.key] === "number" ? (values[def.key] as number) : undefined}
              onChange={(v) => set(def.key, v)}
            />
          );
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
                  {optionLabel(t, o)}
                </option>
              ))}
            </SelectField>
          );
        if (def.type === "multi_select") {
          const chosen = Array.isArray(values[def.key]) ? (values[def.key] as string[]) : [];
          return (
            <fieldset key={def.key} className="ds-field field-choices">
              <legend>{label}</legend>
              {(def.options ?? []).map((o) => (
                <CheckboxField
                  key={o}
                  label={optionLabel(t, o)}
                  checked={chosen.includes(o)}
                  onChange={(e) =>
                    set(def.key, e.target.checked ? [...chosen, o] : chosen.filter((x) => x !== o))
                  }
                />
              ))}
            </fieldset>
          );
        }
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
              {error ? (
                <span className="ds-field__error" role="alert">
                  {error}
                </span>
              ) : null}
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
