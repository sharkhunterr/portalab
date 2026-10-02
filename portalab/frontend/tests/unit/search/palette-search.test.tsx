import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// 008 T030 — the palette adds, for the typed text: the referenced object (opened directly), inline search
// results, "search for …" and assistant suggestions (labelled, never auto-run); sensitive actions ask for
// a second confirmation before running; a failing search source never removes local commands.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { json } from "../../support/fake-api";
import { renderShell, VIEW } from "../shell/harness";

const RESOLUTION = {
  destinations: [],
  actions: [
    {
      id: "identity.delete",
      label: "Delete my account",
      kind: "navigate",
      route: "/account",
      action_id: null,
      sensitivity: "sensitive",
      confirmation_required: true,
      keywords: [],
    },
  ],
  object: { kind: "tickets", id: "123", title: "Printer", route: "/services/123" },
  intent: null,
  suggestions: [{ label: "Uptime", route: "/services", command_key: null, query: null }],
  assistant: "ok",
};

function backend(options: { failSearch?: boolean } = {}) {
  fake.handler = (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/palette/resolve") return options.failSearch ? json(503, {}) : json(200, RESOLUTION);
    if (path === "/api/v1/search/suggest")
      return options.failSearch
        ? json(503, {})
        : json(200, { items: [{ kind: "users", id: "u1", title: "Printer Pat", url_ref: "/account" }] });
    return json(200, VIEW);
  };
}

async function openPalette(text: string) {
  await screen.findByRole("link", { name: "Services" });
  fireEvent.click(screen.getByRole("button", { name: /Search/ }));
  const input = await screen.findByRole("combobox");
  fireEvent.change(input, { target: { value: text } });
  return input;
}

describe("palette search", () => {
  it("offers the object, results, a full search and labelled suggestions", async () => {
    backend();
    const { router } = renderShell();
    const input = await openPalette("#123");
    const list = screen.getByRole("listbox");
    await within(list).findByText("Open Printer");
    expect(within(list).getByText("Printer Pat")).toBeTruthy();
    expect(within(list).getByText("Search for “#123”")).toBeTruthy();
    expect(within(list).getByText("Uptime · Suggested by the assistant")).toBeTruthy();
    const options = within(list).getAllByRole("option");
    const index = options.findIndex((o) => o.textContent === "Open Printer");
    for (let i = 0; i < index; i++) fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(router.state.location.pathname).toBe("/services/123");
  });

  it("asks for confirmation before a sensitive action", async () => {
    backend();
    const { router } = renderShell();
    await openPalette("delete");
    const list = screen.getByRole("listbox");
    fireEvent.click(await within(list).findByText("Delete my account"));
    const confirm = await screen.findByRole("alert");
    expect(confirm.textContent).toContain("needs confirmation");
    expect(router.state.location.pathname).toBe("/");
    fireEvent.click(within(confirm).getByRole("button", { name: "Delete my account" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/account"));
  });

  it("keeps local commands when search is down", async () => {
    backend({ failSearch: true });
    renderShell();
    await openPalette("acc");
    const list = screen.getByRole("listbox");
    expect(within(list).getAllByRole("option")[0]).toHaveTextContent("Account");
  });
});
