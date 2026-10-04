import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LiveProgress } from "../../../src/design-system/admin/AdminKit";

// 027 — a running task shows a spinner, what it did so far and a bar: determinate with a known total,
// indeterminate otherwise; announced politely (role=status).
describe("LiveProgress", () => {
  it("shows how far a task got when the total is known", () => {
    render(<LiveProgress label="Syncing" done={1500} total={6000} detail="1,500 / 6,000" />);
    expect(screen.getByRole("status")).toHaveTextContent("Syncing");
    expect(screen.getByRole("status")).toHaveTextContent("1,500 / 6,000");
    expect(screen.getByRole("progressbar", { name: "Syncing" })).toHaveAttribute("aria-valuenow", "25");
  });

  it("is indeterminate without a total", () => {
    render(<LiveProgress label="Reading" done={12} total={null} />);
    const bar = screen.getByRole("progressbar", { name: "Reading" });
    expect(bar).not.toHaveAttribute("aria-valuenow");
    expect(bar).toHaveAttribute("data-indeterminate", "true");
  });
});
