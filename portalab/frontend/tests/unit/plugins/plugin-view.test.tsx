import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { IntlProvider } from "react-intl";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 030 — a plugin's own view talks to Portalab only: its own plugin's routes (never another path), its own
// pages or a title's page, its own surfaces; it is given the member's theme tokens to follow.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { PluginView } from "../../../src/features/plugins/views/PluginView";
import { json } from "../../support/fake-api";

describe("plugin views", () => {
  it("relays only its own routes, pages and surfaces", async () => {
    const asked: string[] = [];
    fake.handler = async (request) => {
      asked.push(new URL(request.url).pathname);
      return json(200, { state: "available", items: [] });
    };
    const opened: string[] = [];
    const router = createMemoryRouter(
      [
        {
          path: "*",
          element: (
            <PluginView
              plugin="forum"
              view="forum.js"
              mode="page"
              title="Forum"
              onOpen={(s) => opened.push(s)}
            />
          ),
        },
      ],
      { initialEntries: ["/plugins/forum/topics"] },
    );
    render(
      <IntlProvider locale="en" messages={{}}>
        <QueryClientProvider client={new QueryClient()}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </IntlProvider>,
    );
    const frame = document.querySelector("iframe.plugin-view") as HTMLIFrameElement;
    expect(frame.getAttribute("sandbox")).toBe("allow-scripts");
    const answers: unknown[] = [];
    vi.spyOn(frame.contentWindow as Window, "postMessage").mockImplementation((message: unknown) => {
      answers.push(message);
    });
    const say = (data: Record<string, unknown>) =>
      window.dispatchEvent(new MessageEvent("message", { data, source: frame.contentWindow }));

    say({ type: "call", id: 1, method: "GET", path: "topics", query: { q: "x" } });
    say({ type: "call", id: 2, method: "GET", path: "../../admin/plugins", query: null });
    say({ type: "call", id: 3, method: "DELETE", path: "topics", query: null });
    await waitFor(() => expect(answers.length).toBe(3));
    expect(asked).toEqual(["/api/v1/plugins/forum/topics"]);
    const refused = answers.filter((a) => (a as { ok: boolean }).ok === false);
    expect(refused).toHaveLength(2);

    say({ type: "navigate", to: "/admin/plugins" });
    say({ type: "navigate", to: "https://example.org" });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(router.state.location.pathname).toBe("/plugins/forum/topics");
    say({ type: "navigate", to: "/plugins/forum/topic?topic=3" });
    await waitFor(() => expect(router.state.location.search).toBe("?topic=3"));

    say({ type: "open", surface: "compose", params: {} });
    say({ type: "open", surface: "../x", params: {} });
    await waitFor(() => expect(opened).toEqual(["compose"]));
  });
});
