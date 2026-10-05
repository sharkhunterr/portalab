import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import "../../../src/features/dashboard/widgets/calendar";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";

// 027 — the calendar widget: the month as a grid with a mark on busy days, today highlighted; choosing a
// day lists what happens that day, « coming up » otherwise.

const payload = {
  state: "available",
  data: {
    month: "2026-10-01",
    today: "2026-10-05",
    days: {
      "2026-10-05": [
        { title: "Maintenance", kind: "maintenance", time: null, route: "/calendar", date: "2026-10-05" },
      ],
      "2026-10-12": [
        { title: "Dune 3", kind: "media_release", time: null, route: "/media/x", date: "2026-10-12" },
      ],
    },
    upcoming: [{ title: "Dune 3", kind: "media_release", time: null, route: "/media/x", date: "2026-10-12" }],
  },
};

describe("calendar widget", () => {
  it("draws the month, marks busy days and lists a chosen day", () => {
    const Calendar = widgetComponent("calendar.month");
    expect(Calendar).toBeDefined();
    const Component = Calendar as NonNullable<typeof Calendar>;
    render(
      <RouterProvider
        router={createMemoryRouter([
          { path: "/", element: <Component payload={payload as never} config={{ show: "all" }} /> },
        ])}
      />,
    );
    const days = screen.getAllByRole("button");
    expect(days).toHaveLength(31);
    expect(screen.getByRole("link", { name: "Dune 3" })).toBeTruthy(); // coming up
    const today = days[4] as HTMLElement;
    expect(today.getAttribute("data-today")).toBe("true");
    fireEvent.click(today);
    expect(today.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("link", { name: "Maintenance" })).toBeTruthy();
  });
});
