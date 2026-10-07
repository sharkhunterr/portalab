import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fromNavigation, rank } from "../../../src/shell/palette/CommandRegistry";
import { label } from "../../../src/shell/strings";

// 004 T024/T027 (unit part) — the palette lists only the server-filtered commands, matches fuzzily, runs
// actions or navigates with the keyboard, and announces results.

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
import { renderShell, VIEW } from "./harness";

describe("command palette", () => {
  it("ranks fuzzily and keeps unknown actions out", () => {
    const commands = fromNavigation(
      [...VIEW.commands, { key: "x.secret", label_key: "x", kind: "action", action_id: "unknown.action" }],
      label,
      { "shell.show_shortcuts": () => undefined },
    );
    expect(commands.map((c) => c.id)).not.toContain("x.secret");
    expect(rank(commands, "srv")[0]?.label).toBe("Services");
    expect(rank(commands, "profile")[0]?.label).toBe("Account"); // keyword match
  });

  it("is keyboard operable and navigates", async () => {
    fake.handler = () => json(200, VIEW);
    const { router } = renderShell();
    await screen.findByRole("link", { name: "Services" });
    const input = screen.getByRole("combobox", { name: /Search/ }); // 027: the header's search
    fireEvent.change(input, { target: { value: "acc" } });
    const list = await screen.findByRole("listbox");
    expect(within(list).getAllByRole("option")[0]).toHaveTextContent("Account");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(router.state.location.pathname).toBe("/account");
    expect(await screen.findByTestId("announce-polite")).toBeInTheDocument();
  });
});
