import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 030 T029/T030 — a confined plugin's page: the address's parameters reach its data and forms, a thread is
// drawn by Portalab, links stay inside the plugin's own pages, and a committing form is sent only once the
// member confirmed the exact content in Portalab's own dialog (cancelling sends nothing).

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import PageRenderer, { ownLink } from "../../../src/features/plugins/pages/PageRenderer";
import { json } from "../../support/fake-api";

const PAGE = {
  plugin: "forum",
  key: "topic",
  title_key: "Topic",
  blocks: [
    { kind: "thread", title_key: "Messages", data: "thread", columns: [], chart: "line" },
    {
      kind: "form",
      title_key: "Reply",
      action: "replies",
      schema: {
        type: "object",
        properties: { body: { type: "string", format: "textarea" } },
        required: ["body"],
      },
      submit_key: "plugins:page.submit",
    },
  ],
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/plugins/:pluginKey/:pageKey", element: <PageRenderer /> }], {
          initialEntries: ["/plugins/forum/topic?topic=7"],
        })}
      />
    </QueryClientProvider>,
  );
}

describe("confined plugin pages", () => {
  it("keeps links inside the plugin's own pages", () => {
    expect(ownLink("forum", "/plugins/forum/topic?topic=1")).toBe("/plugins/forum/topic?topic=1");
    for (const outside of [
      "/admin/plugins",
      "https://example.org",
      "/plugins/other/x",
      "/plugins/forum/../../admin",
    ])
      expect(ownLink("forum", outside)).toBeNull();
  });

  it("confirms a committing form in Portalab's dialog before sending it", async () => {
    const posts: Array<{ body: unknown; token: string | null }> = [];
    let threadQuery = "";
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/plugins/forum/pages/topic") return json(200, PAGE);
      if (url.pathname === "/api/v1/plugins/forum/thread") {
        threadQuery = url.search;
        return json(200, {
          state: "available",
          title: "Movie night",
          items: [{ id: 1, author: "Ana", body: "Friday?" }],
        });
      }
      if (url.pathname === "/api/v1/plugins/forum/replies") {
        const token = request.headers.get("X-Portalab-Confirmation");
        posts.push({ body: await request.json(), token });
        if (!token)
          return json(409, {
            code: "plugin.confirmation_required",
            title: "Confirm",
            confirmation: "tok-1",
            summary: { title: "Publish this reply?", lines: ["Me too"] },
          });
        return json(200, { state: "available", message: "Replied." });
      }
      return json(404, {});
    };
    show();
    expect(await screen.findByText("Friday?")).toBeInTheDocument();
    expect(threadQuery).toContain("topic=7");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Me too" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Publish this reply?" })).toBeInTheDocument();
    expect(within(dialog).getByText("Me too")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: /confirm/i }));
    expect(await screen.findByText("Replied.")).toBeInTheDocument();
    expect(posts).toEqual([
      { body: { topic: "7", body: "Me too" }, token: null },
      { body: { topic: "7", body: "Me too" }, token: "tok-1" },
    ]);
  });

  it("sends nothing when the member cancels", async () => {
    const tokens: Array<string | null> = [];
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/plugins/forum/pages/topic") return json(200, PAGE);
      if (url.pathname === "/api/v1/plugins/forum/thread") return json(200, { state: "no-data", items: [] });
      tokens.push(request.headers.get("X-Portalab-Confirmation"));
      return json(409, {
        code: "plugin.confirmation_required",
        confirmation: "tok-2",
        summary: { title: "Publish this reply?", lines: ["x"] },
      });
    };
    show();
    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /cancel/i }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(tokens).toEqual([null]);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
