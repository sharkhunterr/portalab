import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 271: a reload brings the radio's player back paused, with its volume (a touch on play tunes in
// again) — not once closed, nor when the radio is gone.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { RadioHost } from "../../../src/features/media/radio/RadioHost";
import { closeRadio, useRadioPlayback } from "../../../src/features/media/radio/store";
import { json } from "../../support/fake-api";

function Volume() {
  return <output data-testid="volume">{useRadioPlayback().volume}</output>;
}

function show(available = true) {
  fake.handler = () =>
    json(
      200,
      available
        ? { available: true, station: "Retro Rock", on_air: true, upcoming: [], recent: [] }
        : { available: false },
    );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RadioHost />
        <Volume />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  closeRadio();
  localStorage.clear();
});

describe("issue 271 — the radio after a reload", () => {
  it("comes back paused with its volume", async () => {
    localStorage.setItem("portalab.radio", JSON.stringify({ open: true, volume: 0.3 }));
    show();
    expect(await screen.findByRole("region", { name: "Radio player" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Listen" })).toBeTruthy();
    expect(screen.getByTestId("volume").textContent).toBe("0.3");
  });

  it("stays away once closed", async () => {
    localStorage.setItem("portalab.radio", JSON.stringify({ open: true, volume: 0.8 }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Close the radio" }));
    expect(JSON.parse(localStorage.getItem("portalab.radio") ?? "{}").open).toBe(false);
    expect(screen.queryByRole("region", { name: "Radio player" })).toBeNull();
  });

  it("goes when the radio is no longer there", async () => {
    localStorage.setItem("portalab.radio", JSON.stringify({ open: true, volume: 0.8 }));
    show(false);
    expect(screen.getByRole("region", { name: "Radio player" })).toBeTruthy();
    await waitFor(() => expect(screen.queryByRole("region", { name: "Radio player" })).toBeNull());
  });
});
