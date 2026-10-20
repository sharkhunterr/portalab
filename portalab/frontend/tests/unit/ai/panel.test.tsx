import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 018 T012/T017/T025 — the panel streams an answer as text (never HTML), shows sources, page suggestions
// and the confirmation card; confirm posts once and announces the outcome; unavailable is explained;
// refusals before streaming (rate limit) are shown politely.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { AiPanel } from "../../../src/features/ai/panel/AiPanel";
import { AnswerText } from "../../../src/features/ai/panel/AnswerText";
import { AssistantFab } from "../../../src/features/ai/panel/AssistantFab";
import { ShellSlotsProvider } from "../../../src/shell/slots/providers";
import { json } from "../../support/fake-api";

const CONVERSATION = {
  id: "c1",
  title: "",
  context: {},
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-01T12:00:00Z",
};
const ACTION = {
  id: "a1",
  tool: "demo.purge",
  summary: "Purge 3 old items",
  status: "pending",
  expires_at: new Date(Date.now() + 600_000).toISOString(),
  created_at: "2026-10-01T12:00:00Z",
  conversation_id: "c1",
  result: null,
};

function sse(events: Array<[string, unknown]>): Response {
  const body = events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join("");
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function show(available = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <AiPanel open onOpenChange={() => undefined} available={available} autoNavigate={false} />,
      },
      { path: "/services", element: <p>Services page</p> },
    ],
    { initialEntries: ["/"] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("AiPanel", () => {
  it("streams, attributes, suggests pages and confirms actions", async () => {
    const posts: string[] = [];
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "POST") posts.push(path);
      if (path === "/api/v1/ai/conversations" && request.method === "GET") return json(200, []);
      if (path === "/api/v1/ai/conversations") return json(201, CONVERSATION);
      if (path.endsWith("/messages"))
        return sse([
          ["tool_call", { id: "t1", name: "services.status" }],
          ["delta", { text: "<b>Media</b> is " }],
          ["delta", { text: "down [1]" }],
          [
            "pending_action",
            { id: "a1", tool: "demo.purge", summary: "Purge 3 old items", expires_at: ACTION.expires_at },
          ],
          [
            "done",
            {
              content: "<b>Media</b> is down [1]",
              sources: [
                {
                  n: 1,
                  kind: "page",
                  ref: "page:health.services",
                  title: "Services",
                  class: "real",
                  as_of: null,
                  url: "/services",
                },
              ],
              caveats: [],
              interpretation: false,
              pending_actions: ["a1"],
            },
          ],
        ]);
      if (path === "/api/v1/ai/actions/a1") return json(200, ACTION);
      if (path === "/api/v1/ai/actions/a1/confirm") return json(200, { ...ACTION, status: "executed" });
      return json(404, {});
    };
    show();
    fireEvent.change(screen.getByLabelText("Ask the assistant…"), { target: { value: "is media up?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(document.querySelector(".ai-answer")?.textContent).toBe("<b>Media</b> is down 1"),
    );
    expect(document.querySelector(".ai-log b")).toBeNull(); // the model's markup is text, never HTML
    expect(document.querySelector(".ai-cite")?.getAttribute("href")).toBe("/services"); // [1] → its source
    expect(screen.queryByText(/services\.status/)).toBeNull(); // issue 171: tools are never named
    expect(screen.getByRole("link", { name: "Services" })).toBeTruthy();
    expect(await screen.findByText("Purge 3 old items")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    const status = await screen.findByRole("status");
    expect(status.textContent).toBe("Done.");
    await waitFor(() => expect(document.activeElement).toBe(status));
    expect(posts.filter((p) => p.endsWith("/confirm"))).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Open Services" }));
    expect(await screen.findByText("Services page")).toBeTruthy();
  });

  it("explains refusals and unavailability", async () => {
    fake.handler = (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "GET") return json(200, []);
      if (path === "/api/v1/ai/conversations") return json(201, CONVERSATION);
      return json(429, { code: "ai.rate_limited", title: "Too many messages" });
    };
    show();
    fireEvent.change(screen.getByLabelText("Ask the assistant…"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("You are sending messages too quickly. Wait a moment.")).toBeTruthy();
  });

  it("shows the unavailable state", () => {
    fake.handler = () => json(200, []);
    show(false);
    expect(
      screen.getByText("The assistant is unavailable right now. Everything else keeps working."),
    ).toBeTruthy();
    expect(screen.queryByLabelText("Ask the assistant…")).toBeNull();
  });
});

describe("the assistant's window (issue 171)", () => {
  it("lays an answer out: bold, lists, the portal's pages as links — never another site's", () => {
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: (
            <AnswerText
              text={
                "**Heat** waits:\n- requested [1]\n- [see it](/media/m1) or [elsewhere](https://evil.example)\n\nDone."
              }
              sources={[
                {
                  n: 1,
                  kind: "media",
                  ref: "m",
                  title: "Heat",
                  class: "real",
                  as_of: null,
                  url: "/media/m1",
                },
              ]}
            />
          ),
        },
      ],
      { initialEntries: ["/"] },
    );
    render(<RouterProvider router={router} />);
    expect(screen.getByText("Heat").tagName).toBe("STRONG");
    expect(document.querySelectorAll(".ai-answer li")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "see it" }).getAttribute("href")).toBe("/media/m1");
    expect(screen.queryByRole("link", { name: "elsewhere" })).toBeNull();
    expect(document.querySelectorAll(".ai-answer li")[1]?.textContent).toBe("see it or elsewhere");
    expect(screen.getByText("Done.")).toBeTruthy();
  });

  it("asks the question it was opened with, with the page as context and nothing else", async () => {
    const bodies: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "GET") return json(200, []);
      if (path === "/api/v1/ai/conversations") {
        bodies.push(await request.json());
        return json(201, CONVERSATION);
      }
      if (path.endsWith("/messages"))
        return sse([
          [
            "done",
            { content: "On its way.", sources: [], caveats: [], interpretation: true, pending_actions: [] },
          ],
        ]);
      return json(404, {});
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter(
      [
        {
          path: "/media/m1",
          element: (
            <AiPanel
              open
              onOpenChange={() => undefined}
              available
              autoNavigate={false}
              context={{ route: "/media/m1", question: "Where is it?", asked: 1 }}
            />
          ),
        },
      ],
      { initialEntries: ["/media/m1"] },
    );
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("On its way.")).toBeTruthy();
    expect(screen.getByText("Where is it?")).toBeTruthy();
    expect(bodies).toEqual([{ context: { route: "/media/m1" } }]); // never the question in the context
  });

  it("opens from its round button on any page", () => {
    const open = vi.fn();
    const router = createMemoryRouter([{ path: "/wiki", element: <AssistantFab hidden={false} /> }], {
      initialEntries: ["/wiki"],
    });
    render(
      <ShellSlotsProvider value={{ ai: { available: true, open } }}>
        <RouterProvider router={router} />
      </ShellSlotsProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Ask the assistant" }));
    expect(open).toHaveBeenCalledWith({ route: "/wiki" });
  });
});
