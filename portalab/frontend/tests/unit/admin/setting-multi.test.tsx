import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 478 — a setting of several of a few (the countries whose ratings count too) is edited with one box
// each: ticking one saves the list with it, in the order the choices come.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { SettingCard } from "../../../src/features/admin/ConfigEditor";
import { json } from "../../support/fake-api";

describe("a setting of several choices", () => {
  it("ticks a box and saves the list", async () => {
    const written: Array<{ changes: Array<{ value: unknown }> }> = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/config/validate") return json(200, { ok: true, errors: [], diff: [] });
      if (request.method === "PUT" && path === "/api/v1/admin/config") {
        written.push(await request.json());
        return json(200, {});
      }
      return json(200, {});
    };
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ul>
          <SettingCard
            item={{
              key: "media.ratings.alsoCountries",
              description: "Other countries",
              sensitive: false,
              value: ["DE"],
              source: "global",
              default: [],
              kind: "multi",
              choices: ["DE", "GB", "US"],
            }}
          />
        </ul>
      </QueryClientProvider>,
    );
    const germany = screen.getByRole("checkbox", { name: "Germany" });
    expect(germany).toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: "United States" }));
    await waitFor(() => expect(written).toHaveLength(1));
    expect(written[0]?.changes[0]?.value).toEqual(["DE", "US"]);
  });
});
