import type { ReactNode } from "react";

/**
 * Policy-bounded preference display (spec 022 T033, FR-006/023): a setting may be locked, mandatory,
 * disabled or conditional by admin policy; the control says so and why, and the user's own choice is
 * kept (shown as "retained") so it applies again when the policy relaxes.
 */
export type PolicyState = "free" | "locked" | "mandatory" | "disabled" | "conditional";

export const policyStrings = {
  locked: "Set by your administrator.",
  mandatory: "Required by your administrator.",
  disabled: "Not available on this portal.",
  conditional: "Only available under some conditions.",
  retained: (value: string) => `Your choice (${value}) is kept and will apply again if the policy changes.`,
} as const;

export interface PolicyFieldProps {
  state: PolicyState;
  reason?: string;
  retainedValue?: string | null;
  children: (props: { disabled: boolean; describedBy?: string | undefined }) => ReactNode;
  id: string;
}

export function PolicyField({ state, reason, retainedValue, children, id }: PolicyFieldProps) {
  const noteId = state === "free" ? undefined : `${id}-policy`;
  const disabled = state === "locked" || state === "disabled";
  return (
    <div data-policy={state}>
      {children({ disabled, describedBy: noteId })}
      {noteId ? (
        <p id={noteId} className="ds-policy">
          {reason ?? policyStrings[state as Exclude<PolicyState, "free">]}
          {retainedValue ? ` ${policyStrings.retained(retainedValue)}` : null}
        </p>
      ) : null}
    </div>
  );
}
