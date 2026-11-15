import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import {
  dayLimitsOf,
  type Plan,
  planOf,
  ScreenPlanner,
  type Span,
  spansOf,
} from "../../../src/features/household/ScreenPlanner";

// Issue 436 — a profile's screen time as a week calendar, like an agenda: a tap puts a one-hour span down, a
// drag draws a longer one, a span moves (to another day too) and lengthens by its lower edge; its card sets
// its hours, its time and the days it is on; each day's maximum sits in its header.

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

/** The calendar laid out: 100 px an hour from the top, 100 px a day from the left. */
function layOut(container: HTMLElement) {
  const body = container.querySelector<HTMLElement>(".screen-cal__body") as HTMLElement;
  body.getBoundingClientRect = () => ({ top: 0, height: 2400, left: 0, width: 700 }) as DOMRect;
  const days = [...container.querySelectorAll<HTMLElement>(".screen-cal__day")];
  days.forEach((column, day) => {
    column.getBoundingClientRect = () =>
      ({ top: 0, height: 2400, left: day * 100, right: day * 100 + 100, width: 100 }) as DOMRect;
  });
  return { body, days };
}
const slots = (seen: Plan[]) => (seen.at(-1)?.slots ?? []) as Span[];

describe("the screen-time calendar", () => {
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

  it("puts a one-hour span down where a free hour is tapped, and opens its card", () => {
    const seen: Plan[] = [];
    const { container } = render(<Harness start={{}} seen={seen} />);
    const { days } = layOut(container);
    fireEvent.pointerDown(days[4] as HTMLElement, { button: 0, clientX: 450, clientY: 1460, pointerId: 1 });
    fireEvent.pointerUp(days[4] as HTMLElement, { clientX: 450, clientY: 1460, pointerId: 1 });
    expect(slots(seen)).toEqual([{ day: 4, start: "14:30", end: "15:30", minutes: null }]);
    expect(screen.getByRole("dialog", { name: "Span on Friday" })).toBeTruthy();
  });

  it("draws a longer span with a drag, snapped to quarter hours", () => {
    const seen: Plan[] = [];
    const { container } = render(<Harness start={{}} seen={seen} />);
    const { body, days } = layOut(container);
    fireEvent.pointerDown(days[2] as HTMLElement, { button: 0, clientX: 250, clientY: 1400, pointerId: 1 });
    fireEvent.pointerMove(body, { clientX: 250, clientY: 1720, pointerId: 1 }); // 17:12 → 17:15
    fireEvent.pointerUp(body, { clientX: 250, clientY: 1720, pointerId: 1 });
    expect(slots(seen)).toEqual([{ day: 2, start: "14:00", end: "17:15", minutes: null }]);
  });

  it("moves a span to another day and hour, and lengthens it by its lower edge", () => {
    const seen: Plan[] = [];
    const { container } = render(
      <Harness start={{ slots: [{ day: 2, start: "10:00", end: "12:00", minutes: 30 }] }} seen={seen} />,
    );
    const { body } = layOut(container);
    const label = screen.getByRole("button", { name: "Wednesday, 10:00 to 12:00: 30 min" });
    fireEvent.pointerDown(label, { button: 0, clientX: 250, clientY: 1050, pointerId: 1 }); // grabbed at 10:30
    fireEvent.pointerMove(body, { clientX: 350, clientY: 1500, pointerId: 1 }); // Thursday, 15:00
    fireEvent.pointerUp(body, { clientX: 350, clientY: 1500, pointerId: 1 });
    expect(slots(seen)).toEqual([{ day: 3, start: "14:30", end: "16:30", minutes: 30 }]);
    layOut(container);
    const edge = container.querySelector<HTMLElement>("[data-edge]") as HTMLElement;
    fireEvent.pointerDown(edge, { button: 0, clientX: 350, clientY: 1630, pointerId: 2 });
    fireEvent.pointerMove(body, { clientX: 350, clientY: 1800, pointerId: 2 });
    fireEvent.pointerUp(body, { clientX: 350, clientY: 1800, pointerId: 2 });
    expect(slots(seen)).toEqual([{ day: 3, start: "14:30", end: "18:00", minutes: 30 }]);
  });

  it("sets a span's hours, its time and the days it is on from its card, at once", () => {
    const seen: Plan[] = [];
    render(<Harness start={{}} seen={seen} />);
    fireEvent.click(screen.getByRole("button", { name: "Add a span" }));
    const card = screen.getByRole("dialog", { name: "Span on Monday" });
    expect((within(card).getByLabelText("From") as HTMLSelectElement).value).toBe(String(16 * 60));
    fireEvent.change(within(card).getByLabelText("To"), { target: { value: String(19 * 60) } });
    fireEvent.click(within(card).getByRole("button", { name: /^1 hr$/ }));
    fireEvent.click(within(card).getByLabelText("Tue"));
    fireEvent.click(within(card).getByLabelText("Thu"));
    expect(slots(seen)).toEqual([
      { day: 0, start: "16:00", end: "19:00", minutes: 60 },
      { day: 1, start: "16:00", end: "19:00", minutes: 60 },
      { day: 3, start: "16:00", end: "19:00", minutes: 60 },
    ]);
    // the same span on its other days follows a change
    fireEvent.change(within(card).getByLabelText("From"), { target: { value: String(15 * 60) } });
    expect(slots(seen).map((s) => `${s.day} ${s.start}`)).toEqual(["0 15:00", "1 15:00", "3 15:00"]);
    fireEvent.click(within(card).getByLabelText("Thu"));
    expect(slots(seen).map((s) => s.day)).toEqual([0, 1]);
    fireEvent.click(within(card).getByRole("button", { name: "Delete the span" }));
    expect(slots(seen)).toEqual([{ day: 1, start: "15:00", end: "19:00", minutes: 60 }]);
  });

  it("sets each day's maximum from its header, « no screen » too", async () => {
    const seen: Plan[] = [];
    render(<Harness start={{}} seen={seen} />);
    const sunday = screen.getByRole("button", { name: /^Most screen time on Sunday/ });
    expect(sunday.textContent).toBe("No max");
    fireEvent.pointerDown(sunday, { button: 0, ctrlKey: false });
    fireEvent.click(await screen.findByRole("menuitem", { name: "No screen" }));
    expect(seen.at(-1)?.week_minutes).toEqual([null, null, null, null, null, null, 0]);
  });

  it("only shows the calendar without « onChange » (a profile's own schedule)", () => {
    const { container } = render(
      <ScreenPlanner plan={{ slots: [{ day: 5, start: "09:00", end: "11:00" }], daily_minutes: 90 }} />,
    );
    expect(screen.queryByRole("button", { name: "Add a span" })).toBeNull();
    expect(container.querySelector("[data-edge]")).toBeNull();
    const span = screen.getByRole("button", { name: "Saturday, 09:00 to 11:00: The whole span" });
    fireEvent.click(span);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getAllByText("1 hr 30 min max")).toHaveLength(7);
  });
});
