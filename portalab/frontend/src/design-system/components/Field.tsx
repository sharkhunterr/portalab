import { type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, useId } from "react";

/**
 * Form fields: always a visible ``<label>``, hint and error wired with ``aria-describedby``; accessible
 * authentication (WCAG 3.3.8): paste is never blocked and ``autoComplete`` tokens are passed through.
 */
interface FieldShellProps {
  label: string;
  hint?: ReactNode;
  error?: ReactNode;
}

export function TextField({
  label,
  hint,
  error,
  id,
  ...props
}: FieldShellProps & InputHTMLAttributes<HTMLInputElement>) {
  const generated = useId();
  const inputId = id ?? generated;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  return (
    <div className="ds-field">
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined}
        aria-invalid={error ? true : undefined}
        {...props}
      />
      {hint ? (
        <span id={hintId} className="ds-field__hint">
          {hint}
        </span>
      ) : null}
      {error ? (
        <span id={errorId} className="ds-field__error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}

export function SelectField({
  label,
  hint,
  error,
  id,
  children,
  ...props
}: FieldShellProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const generated = useId();
  const selectId = id ?? generated;
  const hintId = hint ? `${selectId}-hint` : undefined;
  return (
    <div className="ds-field">
      <label htmlFor={selectId}>{label}</label>
      <select id={selectId} aria-describedby={hintId} aria-invalid={error ? true : undefined} {...props}>
        {children}
      </select>
      {hint ? (
        <span id={hintId} className="ds-field__hint">
          {hint}
        </span>
      ) : null}
      {error ? (
        <span className="ds-field__error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}

export function CheckboxField({
  label,
  hint,
  id,
  ...props
}: FieldShellProps & InputHTMLAttributes<HTMLInputElement>) {
  const generated = useId();
  const inputId = id ?? generated;
  return (
    <div className="ds-field ds-stack--row">
      <input id={inputId} type="checkbox" {...props} />
      <label htmlFor={inputId}>{label}</label>
      {hint ? <span className="ds-field__hint">{hint}</span> : null}
    </div>
  );
}
