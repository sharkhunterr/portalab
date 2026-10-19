import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Issue 158 — the log journal: lines newest first, filtered by level (the request carries it), a line opens
// on its structured fields, a correlation id filters to its lines, live follows « after » the newest line
// and pauses; the exports carry the same filters.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
  requests: [] as Request[],
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  installed.requests = fake.requests;
  return importOriginal();
});

import { LogsAdmin } from "../../src/features/admin/observability/LogsAdmin";
import { json } from "../support/fake-api";

const LINES = [
  {
    seq: 12,
    at: "2026-10-19T10:00:02Z",
    process: "worker",
    level: "ERROR",
    logger: "portalab.connectors.plex.client",
    source: "connector:plex",
    message: "plex answered 500",
    correlation_id: "c0ffee",
    fields: { attempt: 2 },
  },
  {
    seq: 11,
    at: "2026-10-19T10:00:01Z",
    process: "serve",
    level: "INFO",
    logger: "portalab.modules.media.sync",
    source: "media",
    message: "synchronised 12 items",
    correlation_id: null,
    fields: {},
  },
];

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <LogsAdmin />
    </QueryClientProvider>,
  );
}

const urls = () => fake.requests.map((r) => new URL(r.url));

beforeEach(() => {
  fake.requests.length = 0;
  fake.handler = (request) => {
    const url = new URL(request.url);
    const after = url.searchParams.get("after");
    if (after) return json(200, { items: [], sources: null, levels: [] });
    const levels = url.searchParams.getAll("level");
    const correlation = url.searchParams.get("correlation");
    const items = LINES.filter(
      (line) =>
        (!levels.length || levels.includes(line.level)) &&
        (!correlation || line.correlation_id === correlation),
    );
    return json(200, { items, sources: ["connector:plex", "media"], levels: [] });
  };
});

describe("log journal", () => {
  it("shows the lines newest first and filters them by level", async () => {
    show();
    const first = await screen.findByText("plex answered 500");
    const second = screen.getByText("synchronised 12 items");
    expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /ERROR/, pressed: false }));
    await waitFor(() => expect(screen.queryByText("synchronised 12 items")).toBeNull());
    expect(urls().some((u) => u.searchParams.getAll("level").includes("ERROR"))).toBe(true);
    const text = screen.getByRole("link", { name: /Export \(text\)/ });
    expect(text.getAttribute("href")).toContain("level=ERROR");
  });

  it("opens a line on its fields and filters by its correlation", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: /plex answered 500/ }));
    expect(screen.getByText(/"attempt": 2/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "c0ffee" }));
    await waitFor(() =>
      expect(urls().some((u) => u.searchParams.get("correlation") === "c0ffee")).toBe(true),
    );
    expect(await screen.findByText(/Only the lines of correlation c0ffee/)).toBeTruthy();
  });

  it("follows live after the newest line, and pauses", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      show();
      await screen.findByText("plex answered 500");
      await vi.advanceTimersByTimeAsync(3_100);
      await waitFor(() => expect(urls().some((u) => u.searchParams.get("after") === "12")).toBe(true));
      fireEvent.click(screen.getByRole("button", { name: /Pause/ }));
      expect(screen.getByRole("status")).toHaveTextContent("Paused");
      const before = fake.requests.length;
      await vi.advanceTimersByTimeAsync(6_500);
      expect(fake.requests.length).toBe(before);
    } finally {
      vi.useRealTimers();
    }
  });
});
