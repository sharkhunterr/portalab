import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Issue 349: « Mon fil » suggests the sources the administrator listed — followed in one click, then gone.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { SourceSuggestions } from "../../src/features/news/MySources";
import { json } from "../support/fake-api";

const SUGGESTED = [
  { name: "Écrans", url: "https://news.example.org/feed.xml", kind: "rss" },
  { name: "Une chaîne", url: "https://www.youtube.com/feeds/videos.xml?channel_id=x", kind: "youtube" },
];

function show(offered: typeof SUGGESTED) {
  const followed: string[] = [];
  fake.handler = async (request) => {
    const url = new URL(request.url);
    if (url.pathname === "/api/v1/me/news/suggestions")
      return json(
        200,
        offered.filter((s) => !followed.includes(s.url)),
      );
    if (url.pathname === "/api/v1/me/news/sources" && request.method === "POST") {
      followed.push(((await request.json()) as { url: string }).url);
      return json(200, {});
    }
    return json(200, []);
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <SourceSuggestions />
    </QueryClientProvider>,
  );
  return { followed, view };
}

describe("suggested sources", () => {
  it("follows a suggestion in one click, which then leaves the list", async () => {
    const { followed } = show(SUGGESTED);
    const button = await screen.findByRole("button", { name: /Écrans/ });
    expect(screen.getByRole("button", { name: /Une chaîne/ })).toBeTruthy();
    fireEvent.click(button);
    await vi.waitFor(() => expect(followed).toEqual(["https://news.example.org/feed.xml"]));
    await vi.waitFor(() => expect(screen.queryByRole("button", { name: /Écrans/ })).toBeNull());
    expect(screen.getByRole("button", { name: /Une chaîne/ })).toBeTruthy();
  });

  it("shows nothing when nothing is suggested", async () => {
    const { view } = show([]);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(view.container.innerHTML).toBe("");
  });
});
