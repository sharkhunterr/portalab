import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 168 — the homelab's radio: what plays with its cover, listen, ask the DJ and follow the request.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import type { Radio } from "../../../src/features/media/radio/api";
import { RadioCard } from "../../../src/features/media/radio/RadioCard";
import { json } from "../../support/fake-api";

const RADIO: Radio = {
  available: true,
  station: "Retro Rock",
  on_air: true,
  host: "Gus",
  listeners: 1,
  current: { title: "Way of the World", artist: "Genesis", album: "We Can't Dance", cover_ref: "abc" },
  upcoming: [],
  recent: [{ title: "Walk of Life", artist: "Dire Straits" }],
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RadioCard radio={RADIO} history />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RadioCard", () => {
  it("shows what plays and asks the DJ, following the request until it is queued", async () => {
    const asked: unknown[] = [];
    let polls = 0;
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/media/radio/requests" && request.method === "POST") {
        asked.push(await request.json());
        return json(200, { id: "r1", status: "pending" });
      }
      if (path === "/api/v1/media/radio/requests/r1") {
        polls += 1;
        return json(200, { id: "r1", status: "queued", track: { title: "Midnight City" } });
      }
      return json(404, {});
    };
    show();
    expect(screen.getByText("Way of the World")).toBeTruthy();
    expect(screen.getByText(/Genesis/)).toBeTruthy();
    expect(document.querySelector(".radio-card__cover img")?.getAttribute("src")).toBe(
      "/api/v1/media/radio/covers/abc",
    );
    expect(screen.getByRole("button", { name: "Listen" })).toBeTruthy();
    expect(screen.getByText("Walk of Life")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Ask the DJ for a song"), {
      target: { value: "something by M83" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("The DJ is looking…")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Coming up: « Midnight City »")).toBeTruthy(), {
      timeout: 5000,
    });
    expect(asked).toEqual([{ text: "something by M83" }]);
    expect(polls).toBe(1);
  });
});
