import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 171 — the header's search talks to the assistant: a question typed there is offered first as
// « Ask the assistant », Enter asks it (the assistant opens with it); other words keep the results first
// and offer the assistant last; without an assistant, nothing is offered.

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

function backend() {
  fake.handler = (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/search/suggest")
      return json(200, { items: [{ kind: "media", id: "m1", title: "Heat", url_ref: "/media/m1" }] });
    if (path === "/api/v1/palette/resolve") return json(200, { destinations: [], actions: [], object: null });
    return json(200, VIEW);
  };
}

async function type(text: string) {
  await screen.findByRole("link", { name: "Services" });
  const input = screen.getAllByRole("combobox", { name: "Search" })[0] as HTMLInputElement;
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: text } });
  return input;
}

describe("asking the assistant from the search", () => {
  it("offers a question to the assistant first, and asks it on Enter", async () => {
    backend();
    const open = vi.fn();
    renderShell({ slots: { ai: { available: true, open } } });
    const input = await type("Pourquoi Heat n'est pas disponible ?");
    const list = await screen.findByRole("listbox");
    const options = within(list).getAllByRole("option");
    expect(options[0]?.textContent).toContain("Ask the assistant: “Pourquoi Heat n'est pas disponible ?”");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(open).toHaveBeenCalledWith({ route: "/", question: "Pourquoi Heat n'est pas disponible ?" });
  });

  it("keeps the results first for plain words, and offers nothing without an assistant", async () => {
    backend();
    renderShell({ slots: { ai: { available: true, open: vi.fn() } } });
    await type("heat");
    const list = await screen.findByRole("listbox");
    await within(list).findByText("Heat");
    const texts = within(list)
      .getAllByRole("option")
      .map((o) => o.textContent ?? "");
    expect(texts.at(-1)).toContain("Ask the assistant: “heat”");
    expect(texts[0]).not.toContain("Ask the assistant");
  });

  it("offers nothing when no assistant answers", async () => {
    backend();
    renderShell({ slots: { ai: { available: false, open: vi.fn() } } });
    await type("Pourquoi ?");
    const list = await screen.findByRole("listbox");
    expect(within(list).queryByText(/Ask the assistant/)).toBeNull();
  });
});
