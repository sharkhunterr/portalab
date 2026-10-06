import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import "../../../src/features/dashboard/widgets/calendar";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";

// 027 — the calendar widget: the month as a grid, today highlighted, each kind with its colour and icon, an
// event lasting several days drawn as one bar across them; choosing a day lists what happens that day,
// « coming up » otherwise.

const maintenance = {
  title: "Maintenance",
  kind: "maintenance",
  time: null,
  route: "/calendar",
  date: "2026-10-05",
  end: "2026-10-05",
};
const dune = {
  title: "Dune 3",
  kind: "media_release",
  category: "movie",
  time: null,
  route: "/media/x",
  date: "2026-10-12",
  end: "2026-10-12",
};
const festival = {
  title: "Film festival",
  kind: "community_event",
  time: null,
  route: "/community/events",
  date: "2026-10-07",
  end: "2026-10-09",
};
const payload = {
  state: "available",
  data: {
    month: "2026-10-01",
    today: "2026-10-05",
    entries: [maintenance, festival, dune],
    upcoming: [maintenance, festival, dune],
  },
};

describe("calendar widget", () => {
  it("draws the month, marks busy days, spans events and lists a chosen day", () => {
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
    expect(days).toHaveLength(35); // whole weeks, Monday first: 28 Sep → 1 Nov
    expect(screen.getByRole("link", { name: "Dune 3" })).toBeTruthy(); // coming up
    const bar = document.querySelector('.month-grid__bar[data-category="event"]') as HTMLElement;
    expect(bar.style.gridColumn).toBe("3 / 6"); // Wednesday 7 → Friday 9
    expect(document.querySelector('.month-grid__dot[data-category="movie"]')).not.toBeNull();
    const today = days.find((d) => d.getAttribute("data-today")) as HTMLElement;
    expect(today.textContent).toBe("5");
    fireEvent.click(today);
    expect(today.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("link", { name: "Maintenance" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Dune 3" })).toBeNull();
  });
});
