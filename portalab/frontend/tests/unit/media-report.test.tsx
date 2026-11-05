import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 354: « Report a problem » on a media's page — a ticket of the administrator's type, about the media.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { ReportMediaProblem } from "../../src/features/support/tickets/ReportMedia";
import { json } from "../support/fake-api";

const MEDIA_TYPE = {
  key: "media_issue",
  label: "Problem with a media",
  media: true,
  fields: [{ key: "what", label: "What is wrong", type: "select", options: ["Subtitles", "Sound"] }],
};

function show(types: unknown[]) {
  const sent: Array<Record<string, unknown>> = [];
  fake.handler = async (request) => {
    const url = new URL(request.url);
    if (url.pathname === "/api/v1/tickets/types") return json(200, types);
    if (url.pathname === "/api/v1/tickets" && request.method === "POST") {
      sent.push((await request.json()) as Record<string, unknown>);
      return json(201, { id: "t-1" });
    }
    return json(200, []);
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ReportMediaProblem objectId="m-1" title="Alien" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return sent;
}

describe("report a problem with a media", () => {
  it("sends a ticket of the media type, tied to the media", async () => {
    const sent = show([{ key: "bug", label: "Bug", media: false, fields: [] }, MEDIA_TYPE]);
    fireEvent.click(await screen.findByRole("button", { name: /Report a problem/ }));
    fireEvent.change(await screen.findByLabelText(/What is wrong/), { target: { value: "Subtitles" } });
    fireEvent.click(screen.getByRole("button", { name: /Send the report/ }));
    await vi.waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatchObject({
      type_key: "media_issue",
      media_id: "m-1",
      fields: { what: "Subtitles" },
      title: "Problem with “Alien”",
    });
    expect(await screen.findByRole("link", { name: /See my ticket/ })).toBeTruthy();
  });

  it("shows no button when no type takes media reports", async () => {
    show([{ key: "bug", label: "Bug", media: false, fields: [] }]);
    await vi.waitFor(() => expect(screen.queryByRole("button", { name: /Report a problem/ })).toBeNull());
  });
});
