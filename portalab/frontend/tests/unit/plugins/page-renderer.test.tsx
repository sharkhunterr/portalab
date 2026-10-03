import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 023 T030 — PageDefinition blocks render with design-system components only: sanitized Markdown from the
// server, data blocks with functional states, forms generated from a JSON Schema posting to the plugin
// action; an unavailable page shows a state, never a broken slot; no plugin script is executed.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import PageRenderer from "../../../src/features/plugins/pages/PageRenderer";
import { json } from "../../support/fake-api";

const PAGE = {
  plugin: "hello",
  key: "main",
  title_key: "Hello page",
  blocks: [
    { kind: "markdown", html: "<p>A <strong>declarative</strong> page</p>" },
    { kind: "stat", title_key: "Greetings", data: "greetings/count", columns: [], chart: "line" },
    {
      kind: "form",
      title_key: "Greet someone",
      action: "greet",
      schema: { type: "object", properties: { name: { type: "string", maxLength: 40 } }, required: ["name"] },
      submit_key: "plugins:page.submit",
    },
  ],
};

function show(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/plugins/:pluginKey/:pageKey", element }], {
          initialEntries: ["/plugins/hello/main"],
        })}
      />
    </QueryClientProvider>,
  );
}

describe("plugin page renderer", () => {
  it("renders declarative blocks and posts forms to the plugin", async () => {
    const posted: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/plugins/hello/pages/main") return json(200, PAGE);
      if (path === "/api/v1/plugins/hello/greetings/count")
        return json(200, { state: "available", value: 3, label: "greetings" });
      if (path === "/api/v1/plugins/hello/greet") {
        posted.push(await request.json());
        return json(200, { state: "available", message: "Hello, Ada!" });
      }
      return json(404, { code: "not_found" });
    };
    show(<PageRenderer />);
    expect(await screen.findByRole("heading", { level: 1, name: "Hello page" })).toBeTruthy();
    expect(screen.getByText("declarative").tagName).toBe("STRONG");
    expect(await screen.findByText("3")).toBeTruthy();
    expect(document.querySelectorAll("script").length).toBe(0);
    fireEvent.change(screen.getByLabelText("name"), { target: { value: "Ada" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Hello, Ada!")).toBeTruthy();
    await waitFor(() => expect(posted).toEqual([{ name: "Ada" }]));
  });

  it("shows a state when the page is gone or not allowed", async () => {
    fake.handler = () => json(404, { code: "plugin.page_not_found", title: "Not found" });
    show(<PageRenderer />);
    expect(await screen.findByText("This page is not available.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back home" })).toBeTruthy();
  });
});
