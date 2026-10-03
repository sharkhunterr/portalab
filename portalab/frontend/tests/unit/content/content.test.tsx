import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 011 T008/T012/T014/T025 — portal links are annotated per viewer (no title for forbidden targets,
// archived/deleted labelled in text); the wiki editor shows a concurrent change with textual markers and
// lets the editor save on the new version; calendar ranges honour the first day of the week.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { range } from "../../../src/features/calendar/CalendarPage";
import { SafeHtml } from "../../../src/features/content/SafeHtml";
import { PageEditor } from "../../../src/features/wiki/PageEditor";
import { json } from "../../support/fake-api";

function renderAt(path: string, routes: Array<{ path: string; element: ReactNode }>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("SafeHtml", () => {
  it("annotates portal links per viewer", async () => {
    fake.handler = () =>
      json(200, [
        { ref: "portalab://wiki/a", state: "ok", title: "Guide", url: "/wiki/guide" },
        { ref: "portalab://wiki/b", state: "forbidden", title: null, url: null },
        { ref: "portalab://wiki/c", state: "archived", title: "Old", url: "/wiki/old" },
      ]);
    const html =
      '<p><a href="portalab://wiki/a" data-ref="portalab://wiki/a" class="content-ref">guide</a> ' +
      '<a href="portalab://wiki/b" data-ref="portalab://wiki/b" class="content-ref">secret</a> ' +
      '<a href="portalab://wiki/c" data-ref="portalab://wiki/c" class="content-ref">old</a></p>';
    renderAt("/", [{ path: "/", element: <SafeHtml html={html} diagrams={false} /> }]);
    await waitFor(() =>
      expect(screen.getByText("guide").closest("a")?.getAttribute("href")).toBe("/wiki/guide"),
    );
    const secret = screen.getByText("secret").closest("a") as HTMLAnchorElement;
    expect(secret.hasAttribute("href")).toBe(false);
    expect(secret.getAttribute("title")).toBeNull();
    expect(secret.textContent).toContain("(not available)");
    expect(screen.getByText("old").closest("a")?.textContent).toContain("(archived)");
  });
});

describe("wiki editor", () => {
  it("shows a concurrent change and saves on the new version", async () => {
    const puts: Array<Record<string, unknown>> = [];
    const page = {
      id: "p1",
      slug: "guide",
      title: "Guide",
      status: "published",
      parent_id: null,
      position: 0,
      version: 2,
      html: "<p>x</p>",
      body_md: "x",
      language: "en",
      source_language: "en",
      is_translation: false,
      translation_missing: false,
      tags: [],
      audience: { mode: "all", refs: [] },
      readable_by_ai: false,
      help_keys: [],
      updated_at: "2026-10-01T00:00:00Z",
      outline: [],
      breadcrumbs: [],
      can_edit: true,
      warnings: [],
    };
    fake.handler = async (request) => {
      if (request.method === "PUT") {
        const body = (await request.json()) as Record<string, unknown>;
        puts.push(body);
        if (puts.length === 1)
          return json(409, {
            code: "wiki.version_conflict",
            title: "Conflict",
            current_version: 3,
            diff: { lines: [{ op: "insert", text: "someone else's line" }], words: [] },
          });
        return json(200, { ...page, version: 4 });
      }
      return json(200, page);
    };
    renderAt("/wiki/guide/edit", [
      { path: "/wiki/:slug/edit", element: <PageEditor /> },
      { path: "/wiki/:slug", element: <p>saved</p> },
    ]);
    const text = await screen.findByRole("textbox", { name: "Page content" });
    fireEvent.change(text, { target: { value: "my change" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("someone else's line");
    expect(alert.textContent).toContain("added");
    fireEvent.click(screen.getByRole("button", { name: "I have merged the changes" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("saved");
    expect(puts.map((p) => p.base_version)).toEqual([2, 3]);
  });
});

describe("calendar ranges", () => {
  it("aligns months and weeks on the first day of the week", () => {
    const monday = range("week", "2026-10-08", 0); // Thursday → week starts Monday 5th
    expect(monday.days[0]).toBe("2026-10-05");
    const sunday = range("week", "2026-10-08", 6);
    expect(sunday.days[0]).toBe("2026-10-04");
    const month = range("month", "2026-10-08", 0);
    expect(month.days[0]).toBe("2026-09-28");
    expect(month.days).toHaveLength(42);
  });
});
