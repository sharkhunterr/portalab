import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import { daysUntil } from "../../../src/features/dashboard/widgets/layout";
import "../../../src/features/dashboard/widgets/layout";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";

// 027 — layout widgets: a separator with its label, a sticky note in its colour, a countdown in whole days
// (in the member's time zone), a clock; a progress widget is an accessible progress bar.

function show(key: string, data: unknown) {
  const Widget = widgetComponent(key);
  expect(Widget, key).toBeDefined();
  const Component = Widget as NonNullable<typeof Widget>;
  const element: ReactElement = <Component payload={{ state: "available", data } as never} config={{}} />;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element }])} />
    </QueryClientProvider>,
  );
}

describe("layout widgets", () => {
  it("draws a separator with its label and style", () => {
    show("dashboard.separator", { style: "dotted", label: "Media" });
    expect(document.querySelector('.widget-separator[data-style="dotted"]')).not.toBeNull();
    expect(screen.getByText("Media")).toBeInTheDocument();
  });

  it("shows a note in its colour, keeping line breaks", () => {
    show("dashboard.note", { text: "Buy popcorn\nCall Sam", color: "pink" });
    expect(document.querySelector('.widget-note[data-color="pink"]')?.textContent).toBe(
      "Buy popcorn\nCall Sam",
    );
  });

  it("counts whole days to a date", () => {
    const today = new Date("2026-10-07T22:30:00Z");
    expect(daysUntil("2026-10-10", today, "UTC")).toBe(3);
    expect(daysUntil("2026-10-07", today, "UTC")).toBe(0);
    expect(daysUntil("2026-10-01", today, "UTC")).toBe(-6);
    expect(daysUntil("2026-10-10", today, "Pacific/Kiritimati")).toBe(2); // already the 8th there
  });

  it("renders a countdown, a clock and a progress bar", () => {
    show("dashboard.countdown", { label: "Holidays", date: "2999-01-01" });
    expect(document.querySelector(".widget-countdown__days")?.textContent).toMatch(/\d/);
    expect(screen.getByText("Holidays")).toBeInTheDocument();
    show("dashboard.clock", { seconds: true, date: true });
    expect(document.querySelector(".widget-clock__time")).not.toBeNull();
    show("dashboard.progress_vertical", { metric: "level" });
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuemax")).toBe("100");
    expect(document.querySelector('.widget-progress[data-orientation="vertical"]')).not.toBeNull();
  });
});
