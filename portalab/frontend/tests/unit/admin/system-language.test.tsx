import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 451 — the system language and country, set in one place: the current value said, a language and a
// country chosen, the system language, the portal's locale and its language written together.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { SystemLanguage } from "../../../src/features/admin/site/SystemLanguage";
import { json } from "../../support/fake-api";

describe("the system language and country", () => {
  it("says what the portal follows, and sets the language and the country", async () => {
    const written: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/config/validate") return json(200, { ok: true, errors: [], diff: [] });
      if (request.method === "PUT" && path === "/api/v1/admin/config") {
        written.push(await request.json());
        return json(200, {});
      }
      if (path === "/api/v1/admin/config")
        return json(200, {
          settings: [
            { key: "i18n.systemLanguage", value: null, source: "default" },
            { key: "i18n.defaultLocale", value: "en", source: "default" },
            { key: "i18n.defaultLanguage", value: "en", source: "default" },
          ],
        });
      if (path === "/api/v1/i18n/languages")
        return json(200, {
          default: "en",
          items: [
            { code: "en", name_native: "English" },
            { code: "fr", name_native: "Français" },
          ],
        });
      return json(404, {});
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <SystemLanguage />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Not chosen yet: the portal follows en.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Language"), { target: { value: "fr" } });
    expect((screen.getByLabelText("Country") as HTMLSelectElement).value).toBe("FR"); // its likeliest
    fireEvent.click(screen.getByRole("button", { name: "Save the system language" }));
    await waitFor(() => expect(written).toHaveLength(1));
    const keys = (written[0] as { changes: Array<{ key: string; value: string }> }).changes;
    expect(keys.map((c) => [c.key, c.value])).toEqual([
      ["i18n.systemLanguage", "fr-FR"],
      ["i18n.defaultLocale", "fr-FR"],
      ["i18n.defaultLanguage", "fr"],
    ]);
  });
});
