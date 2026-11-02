import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const palette = () => ({ background: "#000", surface: "#111", accent: "#7f9cff", text: "#fff" });

describe("issue 325 — automatic newsletters", () => {
  it("writes one with its name and its subject's variables", async () => {
    const saved: Array<Record<string, unknown>> = [];
    let previews = 0;
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/news/newsletters" && request.method === "POST") {
        saved.push((await request.json()) as Record<string, unknown>);
        return json(201, {});
      }
      if (path === "/api/v1/admin/news/newsletters") return json(200, []);
      if (path === "/api/v1/admin/news/categories")
        return json(200, [{ id: "c1", key: "lettre", name: "La lettre", newsletter: true, enabled: true }]);
      if (path === "/api/v1/admin/news/newsletter-templates")
        return json(200, [
          { key: "portalab", builtin: true, definition: { name: "Portalab", palette: palette() } },
          { key: "cine", builtin: false, definition: { name: "Ciné", palette: palette() } },
        ]);
      if (path === "/api/v1/admin/news/newsletter-contents")
        return json(200, {
          contents: ["stats", "movies"],
          defaults: ["stats"],
          charts: ["figures"],
          chart_defaults: ["figures"],
        });
      if (path === "/api/v1/admin/news/newsletter-editions/preview") {
        previews += 1;
        return json(200, { id: "e1" });
      }
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
    // issue 327: no preview written while typing — the live preview is off by default
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(previews).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: /Generate the preview/ }));
    await waitFor(() => expect(previews).toBe(1));
    // issue 329: its own template, picked by sight
    fireEvent.click(await screen.findByRole("radio", { name: /Ciné/ }));
    // issue 332: in the news, by e-mail, or both — never neither
    fireEvent.click(screen.getByRole("checkbox", { name: /Publish in the portal/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /E-mail it/ }));
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(/at least one/);
    fireEvent.click(screen.getByRole("checkbox", { name: /E-mail it/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0]).toMatchObject({ publish: false, email: true });
    expect(saved[0]).toMatchObject({
      name: "Friday letter",
      kind: "edition",
      category_id: "c1",
      template_key: "cine",
      contents: ["stats"],
    });
    expect(String(saved[0]?.subject)).toContain("{semaine}");
  });

  it("issue 328 — a card switched in place, tested to me, deleted once confirmed", async () => {
    const puts: Array<Record<string, unknown>> = [];
    const calls: string[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/admin/news/newsletters/s1" && request.method === "PUT") {
        puts.push((await request.json()) as Record<string, unknown>);
        return json(200, {});
      }
      if (path === "/api/v1/admin/news/newsletters/s1" && request.method === "DELETE") {
        calls.push("delete");
        return new Response(null, { status: 204 });
      }
      if (path === "/api/v1/admin/news/newsletters")
        return json(200, [
          {
            id: "s1",
            name: "Friday letter",
            subject: "{site} — week {semaine}",
            category_id: "c1",
            kind: "edition",
            media_kinds: [],
            cadence: "weekly",
            weekday: 4,
            hour: 18,
            language: "en",
            email: true,
            enabled: true,
            template_key: "portalab",
            notice: null,
            contents: null,
            charts: null,
            days: null,
            subscribers: 3,
            last_run_at: null,
            next_run_at: null,
            last_article_id: null,
          },
        ]);
      if (path === "/api/v1/admin/news/categories")
        return json(200, [{ id: "c1", key: "lettre", name: "La lettre", newsletter: true, enabled: true }]);
      if (path === "/api/v1/admin/news/newsletter-templates") return json(200, []);
      if (path === "/api/v1/admin/news/newsletter-contents")
        return json(200, { contents: ["stats"], defaults: ["stats"], charts: [], chart_defaults: [] });
      if (path === "/api/v1/admin/news/newsletter-editions/preview") {
        calls.push("preview");
        return json(200, { id: "e1" });
      }
      if (path === "/api/v1/admin/news/newsletter-editions/e1/test") {
        calls.push("test");
        return json(200, { sent: true });
      }
      return json(404, {});
    };
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AutomaticNewsletters />
      </QueryClientProvider>,
    );
    const toggle = await screen.findByRole("checkbox", { name: "On" });
    fireEvent.click(toggle);
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]).toMatchObject({ name: "Friday letter", enabled: false });
    expect(puts[0]).not.toHaveProperty("subscribers");
    expect(puts[0]).not.toHaveProperty("id");

    fireEvent.click(screen.getByRole("button", { name: /Send me a test/ }));
    await waitFor(() => expect(calls).toEqual(["preview", "test"]));

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog");
    expect(calls).not.toContain("delete");
    fireEvent.click(within(dialog).getByRole("button", { name: /Delete/ }));
    await waitFor(() => expect(calls).toContain("delete"));
  });
});
