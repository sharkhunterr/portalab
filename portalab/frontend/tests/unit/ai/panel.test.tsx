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
    expect(document.querySelector("a.ai-card")?.getAttribute("href")).toBe("/services"); // its card
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
                "**Heat** waits:\n- requested [1]\n- [see it](/media/m1) or [elsewhere](https://evil.example)\n\n[made up](/media/7a07167c-b1b2-74a3) and [the shop](/marketplace). Done.\n\nLe prophete blanc_L_Assassin_royal_7"
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
    expect(screen.queryByRole("link", { name: "made up" })).toBeNull(); // an item no source names
    expect(screen.getByText(/blanc_L_Assassin_royal_7/)).toBeTruthy(); // « _ » in a title is no italics
    expect(screen.getByRole("link", { name: "the shop" }).getAttribute("href")).toBe("/marketplace");
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

describe("a message's actions (issue 171)", () => {
  it("copies a message without its source numbers and asks a question again", async () => {
    const asked: string[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "GET") return json(200, []);
      if (path === "/api/v1/ai/conversations") return json(201, CONVERSATION);
      if (path.endsWith("/messages")) {
        asked.push(((await request.json()) as { content: string }).content);
        return sse([
          [
            "done",
            { content: "All good [1].", sources: [], caveats: [], interpretation: true, pending_actions: [] },
          ],
        ]);
      }
      return json(404, {});
    };
    const written: string[] = [];
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (text: string) => written.push(text) },
    });
    show();
    fireEvent.change(screen.getByLabelText("Ask the assistant…"), { target: { value: "Is it all up?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(document.querySelector(".ai-answer")?.textContent).toContain("All good"));
    const copies = screen.getAllByRole("button", { name: "Copy" });
    fireEvent.click(copies[1] as HTMLElement); // the answer
    await waitFor(() => expect(written).toEqual(["All good."]));
    expect(await screen.findByText("Copied")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Send again" }));
    await waitFor(() => expect(asked).toEqual(["Is it all up?", "Is it all up?"]));
  });
});

describe("the member's verdict (issue 176)", () => {
  it("rates an answer, says what was expected and takes a verdict back", async () => {
    const verdicts: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (request.method === "GET") return json(200, []);
      if (path === "/api/v1/ai/conversations") return json(201, CONVERSATION);
      if (path.endsWith("/messages"))
        return sse([
          [
            "done",
            {
              content: "Open your account.",
              sources: [],
              caveats: [],
              interpretation: false,
              pending_actions: [],
              message_id: "m1",
            },
          ],
        ]);
      if (path === "/api/v1/ai/messages/m1/feedback") {
        const body = (await request.json()) as { rating: string | null; comment: string };
        verdicts.push(body);
        return json(200, {
          rating: body.rating === "up" ? 1 : body.rating ? -1 : null,
          comment: body.comment,
        });
      }
      return json(404, {});
    };
    show();
    fireEvent.change(screen.getByLabelText("Ask the assistant…"), { target: { value: "My avatar?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    const down = await screen.findByRole("button", { name: "Not as expected" });
    fireEvent.click(down);
    await waitFor(() => expect(down.getAttribute("aria-pressed")).toBe("true"));
    // the member is told who may read it, and may say what was expected
    expect(screen.getByText(/can be read by the administrators/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("What did you expect? (optional)"), {
      target: { value: "The menu moved" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send my comment" }));
    expect(await screen.findByText("Thanks — your comment was sent.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Not as expected" })); // pressed again: taken back
    await waitFor(() =>
      expect(verdicts).toEqual([
        { rating: "down", comment: "" },
        { rating: "down", comment: "The menu moved" },
        { rating: null, comment: "" },
      ]),
    );
    expect(screen.getByRole("button", { name: "Not as expected" }).getAttribute("aria-pressed")).toBe(
      "false",
    );
  });
});

describe("today's allowance (issue 171)", () => {
  it("shows what is left of it", () => {
    fake.handler = () => json(200, []);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: (
            <AiPanel
              open
              onOpenChange={() => undefined}
              available
              autoNavigate={false}
              name="Nova"
              quota={{ budget: 1000, used: 250 }}
              ideas={["Mes demandes en cours ?"]}
            />
          ),
        },
      ],
      { initialEntries: ["/"] },
    );
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("75 % of today's allowance left")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Nova" })).toBeTruthy();
    // issue 174: the administrators' questions instead of the defaults
    expect(screen.getByRole("button", { name: "Mes demandes en cours ?" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Are all the services working?" })).toBeNull();
  });
});
