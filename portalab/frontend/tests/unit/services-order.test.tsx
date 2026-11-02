import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { ServicesOrder } from "../../src/features/dashboard/edit/ServicesOrder";

// Issue 333: the quick-access widget shows the services ticked, in the order chosen — every service, in the
// usual order, until a choice is made.

const SERVICES = [
  { id: "a", name: "Plex", connector: "plex", state: "operational" },
  { id: "b", name: "Sonarr", connector: "sonarr", state: "degraded" },
  { id: "c", name: "Seerr", connector: "seerr", state: "unavailable" },
];

function Harness({ seen }: { seen: string[][] }) {
  const [value, setValue] = useState<string[]>([]);
  return (
    <ServicesOrder
      label="Services"
      value={value}
      services={SERVICES}
      onChange={(next) => {
        seen.push(next);
        setValue(next);
      }}
    />
  );
}

describe("issue 333 — the services of quick access, chosen and ordered", () => {
  it("ticks, moves and resets", () => {
    const seen: string[][] = [];
    render(<Harness seen={seen} />);
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.every((box) => (box as HTMLInputElement).checked)).toBe(true); // every one by default
    fireEvent.click(screen.getByRole("checkbox", { name: /Sonarr/ }));
    expect(seen.at(-1)).toEqual(["a", "c"]);
    fireEvent.click(screen.getByRole("button", { name: /Move Seerr up/ }));
    expect(seen.at(-1)).toEqual(["c", "a"]);
    fireEvent.click(screen.getByRole("checkbox", { name: /Sonarr/ }));
    expect(seen.at(-1)).toEqual(["c", "a", "b"]);
    fireEvent.click(screen.getByRole("button", { name: /Every service/ }));
    expect(seen.at(-1)).toEqual([]);
    // the usual order, all ticked, is « every service » again
    fireEvent.click(screen.getByRole("button", { name: /Move Plex down/ }));
    fireEvent.click(screen.getByRole("button", { name: /Move Plex up/ }));
    expect(seen.at(-1)).toEqual([]);
  });

  it("never leaves none", () => {
    render(<ServicesOrder label="Services" value={["b"]} services={SERVICES} onChange={() => {}} />);
    expect(screen.getByRole("checkbox", { name: /Sonarr/ })).toBeDisabled();
  });
});
