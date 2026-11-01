import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 325: an automatic newsletter is a self-writing edition on its cadence — its name for the news desk,
// its e-mail's subject with variables (clicked in), what it tells — saved as one.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AutomaticNewsletters } from "../../src/features/news/editions/AutomaticNewsletters";
import { json } from "../support/fake-api";

describe("issue 325 — automatic newsletters", () => {
  it("writes one with its name and its subject's variables", async () => {
    const saved: Array<Record<string, unknown>> = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/news/newsletters" && request.method === "POST") {
        saved.push((await request.json()) as Record<string, unknown>);
        return json(201, {});
      }
      if (path === "/api/v1/admin/news/newsletters") return json(200, []);
      if (path === "/api/v1/admin/news/categories")
        return json(200, [{ id: "c1", key: "lettre", name: "La lettre", newsletter: true, enabled: true }]);
      if (path === "/api/v1/admin/news/newsletter-templates") return json(200, []);
      if (path === "/api/v1/admin/news/newsletter-contents")
        return json(200, {
          contents: ["stats", "movies"],
          defaults: ["stats"],
          charts: ["figures"],
          chart_defaults: ["figures"],
        });
      if (path === "/api/v1/admin/news/newsletter-editions/preview") return json(200, { id: "e1" });
      return json(404, {});
    };
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AutomaticNewsletters />
      </QueryClientProvider>,
    );
    const create = await screen.findAllByRole("button", { name: /New automatic newsletter/ });
    await waitFor(() => expect(create[0]).not.toBeDisabled());
    fireEvent.click(create[0] as HTMLElement);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Friday letter" } });
    fireEvent.change(screen.getByLabelText("E-mail subject"), { target: { value: "Week " } });
    fireEvent.click(screen.getByRole("button", { name: "{semaine}" }));
    await screen.findByRole("checkbox", { name: /Statistics/ }); // the contents offered are there
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0]).toMatchObject({
      name: "Friday letter",
      kind: "edition",
      category_id: "c1",
      template_key: "portalab",
      contents: ["stats"],
    });
    expect(String(saved[0]?.subject)).toContain("{semaine}");
  });
});
