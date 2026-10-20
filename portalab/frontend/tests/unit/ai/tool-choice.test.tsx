import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { ToolChoice } from "../../../src/features/ai/admin/ToolChoice";

// Issue 171 — the assistant's tools in words: grouped by what they read, each saying what it does and
// whether it waits for the member's confirmation; one at a time or a whole group; an extension's tool keeps
// its own description.

const TOOLS = [
  {
    name: "media.status",
    owner: "module:media",
    permission: "media.read",
    sensitivity: "read",
    disabled: false,
    description: "",
  },
  {
    name: "media.my_history",
    owner: "module:media",
    permission: "media.read",
    sensitivity: "read",
    disabled: false,
    description: "",
  },
  {
    name: "support.create_ticket",
    owner: "module:support",
    permission: "tickets.create",
    sensitivity: "sensitive",
    disabled: false,
    description: "",
  },
  {
    name: "playlist.add",
    owner: "plugin:playlist",
    permission: "playlist.use",
    sensitivity: "write",
    disabled: false,
    description: "Add a title to a playlist.",
  },
];

let latest = new Set<string>();
function Harness() {
  const [off, setOff] = useState(new Set<string>());
  latest = off;
  return <ToolChoice tools={TOOLS} disabled={off} onChange={setOff} />;
}

describe("the assistant's tools", () => {
  it("are told in words, by group, on and off", () => {
    render(<Harness />);
    expect(screen.getByText("Where a title stands")).toBeTruthy();
    expect(screen.getByText("Open a ticket")).toBeTruthy();
    expect(screen.getByText("Needs confirmation")).toBeTruthy();
    expect(screen.getByText("Add a title to a playlist.")).toBeTruthy(); // an extension's own words
    expect(screen.getByText("Extensions and others")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "All off" })[0] as HTMLElement); // the media group
    expect([...latest].sort()).toEqual(["media.my_history", "media.status"]);
    fireEvent.click(screen.getByRole("checkbox", { name: /Open a ticket/ }));
    expect(latest.has("support.create_ticket")).toBe(true);
  });
});
