import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PortalUnreachable } from "../../../src/shell/router/PortalUnreachable";

// Issue 16 — the portal does not answer: a page of its own, a new try on its own with a countdown, a
// « Retry » button focused; once the portal answers, the page comes back.

function show(onBack: () => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PortalUnreachable onBack={onBack} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("PortalUnreachable", () => {
  it("explains, counts down, tries again and comes back once the portal answers", async () => {
    let up = false;
    const fetch = vi.fn(async (input: RequestInfo | URL) =>
      String(input).endsWith("/livez")
        ? up
          ? new Response("ok", { status: 200 })
          : Promise.reject(new TypeError("Failed to fetch"))
        : new Response("{}", { status: 503 }),
    );
    vi.stubGlobal("fetch", fetch);
    const onBack = vi.fn();
    show(onBack);
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("The portal is unavailable for a moment")).toBeTruthy();
    const retry = screen.getByRole("button", { name: "Retry" });
    expect(document.activeElement).toBe(retry);
    expect(screen.getByText("Trying again in 5 s…")).toBeTruthy();
    fireEvent.click(retry); // still away: the next try waits longer
    await waitFor(() => expect(screen.getByText("Trying again in 10 s…")).toBeTruthy());
    expect(onBack).not.toHaveBeenCalled();
    up = true;
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    });
    await waitFor(() => expect(onBack).toHaveBeenCalledTimes(1));
  });
});
