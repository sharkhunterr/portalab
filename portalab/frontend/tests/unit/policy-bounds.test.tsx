import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PolicyField, type PolicyState } from "../../src/design-system/components/PolicyField";

// 022 T032 — mandatory/locked/disabled/conditional states are explained; the user's choice is retained
// when the policy narrows; density never changes functional content (covered by a11y-prefs).

function Field({ state, retained }: { state: PolicyState; retained?: string }) {
  return (
    <PolicyField id={`f-${state}`} state={state} retainedValue={retained ?? null}>
      {({ disabled, describedBy }) => (
        <label>
          Theme
          <select disabled={disabled} aria-describedby={describedBy} defaultValue="dark">
            <option value="dark">Dark</option>
          </select>
        </label>
      )}
    </PolicyField>
  );
}

describe("policy-bounded fields", () => {
  it.each([
    ["locked", "Set by your administrator.", true],
    ["disabled", "Not available on this portal.", true],
    ["mandatory", "Required by your administrator.", false],
    ["conditional", "Only available under some conditions.", false],
  ] as const)("%s is explained", (state, note, disabled) => {
    render(<Field state={state} />);
    const select = screen.getByLabelText("Theme");
    expect(select).toHaveAccessibleDescription(note);
    expect((select as HTMLSelectElement).disabled).toBe(disabled);
  });

  it("keeps and shows the user's retained choice", () => {
    render(<Field state="locked" retained="Dark" />);
    expect(screen.getByText(/Your choice \(Dark\) is kept/)).toBeInTheDocument();
  });

  it("a free field has no policy note", () => {
    render(<Field state="free" />);
    expect(screen.getByLabelText("Theme")).not.toHaveAttribute("aria-describedby");
  });
});
