import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import {
  dayLimitsOf,
  planOf,
  ScreenPlanner,
  type Span,
  spansOf,
} from "../../../src/features/household/ScreenPlanner";

// Issue 432 — a profile's screen time as a week planner: spans drawn on each day's line, each its own time,
// and a maximum a day.

type Plan = Parameters<typeof ScreenPlanner>[0]["plan"];

function Harness({ start, seen }: { start: Plan; seen: Plan[] }) {
  const [plan, setPlan] = useState<Plan>(start);
  return (
    <ScreenPlanner
      plan={plan}
      onChange={(next) => {
        seen.push(next);
        setPlan(next);
      }}
    />
  );
}

describe("the screen planner", () => {
  it("turns the old allowed hours into spans, and writes one maximum when every day agrees", () => {
    const spans = spansOf({ hours_from: "20:00", hours_to: "07:00" });
    expect(spans.filter((s) => s.day === 0)).toEqual([
      { day: 0, start: "00:00", end: "07:00", minutes: null },
      { day: 0, start: "20:00", end: "24:00", minutes: null },
    ]);
    expect(dayLimitsOf({ daily_minutes: 60 })).toEqual([60, 60, 60, 60, 60, 60, 60]);
    expect(planOf([], [60, 60, 60, 60, 60, 60, 60])).toMatchObject({ daily_minutes: 60, week_minutes: null });
    expect(planOf([], [30, 30, 30, 30, 60, 0, null])).toMatchObject({
      daily_minutes: null,
      week_minutes: [30, 30, 30, 30, 60, 0, null],
      hours_from: null,
    });
  });

  it("adds a span with « + », gives it a time and copies it to other days", () => {
    const seen: Plan[] = [];
    render(<Harness start={{}} seen={seen} />);
    fireEvent.click(screen.getByRole("button", { name: "Add a span on Monday" }));
    const editor = screen.getByRole("region", { name: "Span on Monday" });
    expect((within(editor).getByLabelText("From") as HTMLInputElement).value).toBe("16:00");
    fireEvent.change(within(editor).getByLabelText("Time in this span"), { target: { value: "60" } });
    fireEvent.click(within(editor).getByLabelText("Tue"));
    fireEvent.click(within(editor).getByRole("button", { name: "Apply" }));
    const last = seen.at(-1)?.slots as Span[];
    expect(last).toEqual([
      { day: 0, start: "16:00", end: "18:00", minutes: 60 },
      { day: 1, start: "16:00", end: "18:00", minutes: 60 },
    ]);
    expect(screen.getByRole("button", { name: "Tuesday, 16:00 to 18:00: 60 min" })).toBeTruthy();
  });

  it("refuses a span overlapping another one of its day", () => {
    const seen: Plan[] = [];
    render(
      <Harness
        start={{
          slots: [
            { day: 2, start: "10:00", end: "12:00" },
            { day: 2, start: "14:00", end: "16:00" },
          ],
        }}
        seen={seen}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Wednesday, 10:00 to 12:00/ }));
    const editor = screen.getByRole("region", { name: "Span on Wednesday" });
    fireEvent.change(within(editor).getByLabelText("To"), { target: { value: "15:00" } });
    expect(within(editor).getByRole("alert").textContent).toContain("overlaps");
    expect((within(editor).getByRole("button", { name: "Apply" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(editor).getByRole("button", { name: "Delete the span" }));
    expect((seen.at(-1)?.slots as Span[]).map((s) => s.start)).toEqual(["14:00"]);
  });

  it("draws a span with the pointer, snapped to half hours", () => {
    const seen: Plan[] = [];
    const { container } = render(<Harness start={{}} seen={seen} />);
    const track = container.querySelectorAll<HTMLDivElement>(".screen-planner__track")[4] as HTMLDivElement;
    track.getBoundingClientRect = () => ({ left: 0, width: 1800, top: 0, height: 40 }) as DOMRect;
    fireEvent.pointerDown(track, { button: 0, clientX: 800, pointerId: 1 }); // 14:00 (the line starts at 6:00)
    fireEvent.pointerMove(track, { clientX: 1120, pointerId: 1 }); // 17:12 → 17:00
    fireEvent.pointerUp(track, { pointerId: 1 });
    expect(seen.at(-1)?.slots).toEqual([{ day: 4, start: "14:00", end: "17:00", minutes: null }]);
  });

  it("sets each day's maximum, « no screen » too", () => {
    const seen: Plan[] = [];
    render(<Harness start={{}} seen={seen} />);
    fireEvent.change(screen.getByLabelText("Most screen time on Sunday"), { target: { value: "0" } });
    expect(seen.at(-1)?.week_minutes).toEqual([null, null, null, null, null, null, 0]);
  });
});
