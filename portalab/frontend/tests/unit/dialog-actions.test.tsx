import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "../../src/design-system/components/Button";
import { Dialog, DialogActions } from "../../src/design-system/components/Overlays";

// 027 — a dialog's actions sit in its footer, on the same line as « Cancel », wherever they are written;
// a submit button still submits its form (and outside a dialog, actions stay where they are).

describe("dialog actions", () => {
  it("puts a form's submit button in the footer, next to Cancel, and it still submits the form", () => {
    const submitted = vi.fn();
    render(
      <Dialog open title="Settings" closeLabel="Cancel" trigger={<button type="button">open</button>}>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submitted();
          }}
        >
          <input aria-label="Name" required defaultValue="x" />
          <DialogActions>
            <Button type="submit">Save</Button>
          </DialogActions>
        </form>
      </Dialog>,
    );
    const save = screen.getByRole("button", { name: "Save" });
    const footer = document.querySelector(".ds-dialog__footer");
    expect(footer?.contains(save)).toBe(true);
    expect(footer?.contains(screen.getByRole("button", { name: "Cancel" }))).toBe(true);
    fireEvent.click(save);
    expect(submitted).toHaveBeenCalledTimes(1);
  });

  it("leaves the actions in place outside a dialog", () => {
    render(
      <form>
        <DialogActions>
          <Button type="submit">Save</Button>
        </DialogActions>
      </form>,
    );
    expect(screen.getByRole("button", { name: "Save" }).closest("form")).not.toBeNull();
  });
});
