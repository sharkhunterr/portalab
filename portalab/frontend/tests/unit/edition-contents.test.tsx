import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

// Issue 323: what an edition tells, as options — the usual ones on until chosen, each switched on or off
// in the edition's own order, « default » bringing the usual ones back.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import type { Content } from "../../src/features/news/editions/api";
import { ContentPicker } from "../../src/features/news/editions/ContentPicker";
import { json } from "../support/fake-api";

let last: Content[] | null = null;
function Harness() {
  const [value, setValue] = useState<Content[] | null>(null);
  return (
    <ContentPicker
      value={value}
      onChange={(next) => {
        last = next;
        setValue(next);
      }}
    />
  );
}

describe("issue 323 — an edition's contents", () => {
  it("switches contents on and off, in the edition's order", async () => {
    fake.handler = () =>
      json(200, {
        contents: ["stats", "movies", "audiobooks", "requests", "tv"],
        defaults: ["stats", "movies", "tv"],
      });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <Harness />
      </QueryClientProvider>,
    );
    const audiobooks = await screen.findByRole("checkbox", { name: /New audiobooks/ });
    expect(audiobooks).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Statistics/ })).toBeChecked();
    fireEvent.click(audiobooks);
    expect(last).toEqual(["stats", "movies", "audiobooks", "tv"]);
    fireEvent.click(screen.getByRole("checkbox", { name: /Statistics/ }));
    expect(last).toEqual(["movies", "audiobooks", "tv"]);
    fireEvent.click(screen.getByRole("button", { name: /default contents/ }));
    expect(last).toEqual(["stats", "movies", "tv"]);
  });
});
