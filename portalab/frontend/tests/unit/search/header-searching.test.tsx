import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// The header's search shows it is searching — from the first letter typed until every answer is in — then
// the button that clears it.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
  release: () => {},
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { json } from "../../support/fake-api";
import { renderShell, VIEW } from "../shell/harness";

describe("the header's search", () => {
  it("spins while it searches, then offers to clear", async () => {
    const answered = new Promise<void>((resolve) => {
      fake.release = resolve;
    });
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/search/suggest") {
        await answered;
        return json(200, { items: [{ kind: "media", id: "m1", title: "Heat", url_ref: "/media/m1" }] });
      }
      if (path === "/api/v1/palette/resolve")
        return json(200, { destinations: [], actions: [], object: null });
      return json(200, VIEW);
    };
    renderShell({ slots: { ai: { available: false, open: vi.fn() } } });
    await screen.findByRole("link", { name: "Services" });
    const input = screen.getAllByRole("combobox", { name: "Search" })[0] as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "heat" } });
    expect(screen.getByRole("status").textContent).toBe("Searching…"); // at once, before asking
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
    fake.release();
    await screen.findByText("Heat");
    await waitFor(() => expect(screen.queryByText("Searching…")).toBeNull());
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
  });
});
