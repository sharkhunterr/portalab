import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// 027 — terms of use: while the version in force is not accepted, a small window asks to accept or refuse
// (refusing signs out, after a confirmation), the terms readable in a modal; accepting opens the portal.
// Nothing to accept (none published, or the administrators asking nothing): the portal shows at once.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { TermsGate } from "../../../src/features/terms/TermsGate";
import { json } from "../../support/fake-api";

const TERMS = {
  version: 2,
  title: "Conditions",
  summary: "A new rule",
  html: "<p>Be kind.</p>",
  requires_acceptance: true,
  published_at: "2026-10-01T12:00:00Z",
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TermsGate>
        <p>The portal</p>
      </TermsGate>
    </QueryClientProvider>,
  );
}

describe("terms gate", () => {
  it("shows the portal when there is nothing to accept", async () => {
    fake.handler = () =>
      json(200, { terms: null, accepted_version: null, accepted_at: null, required: false });
    show();
    expect(await screen.findByText("The portal")).toBeTruthy();
  });

  it("asks to accept or refuse, the terms readable in a modal", async () => {
    let accepted = false;
    const sent: unknown[] = [];
    fake.handler = async (request) => {
      if (request.method === "POST") {
        sent.push(await request.json());
        accepted = true;
      }
      return json(200, {
        terms: TERMS,
        accepted_version: accepted ? 2 : 1,
        accepted_at: null,
        required: !accepted,
      });
    };
    show();
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    expect(screen.queryByText("The portal")).toBeNull();
    expect(screen.getByText("A new rule")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /read the terms/i }));
    expect(await screen.findByText("Be kind.")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: /^refuse$/i })[0] as HTMLElement);
    expect(await screen.findByRole("button", { name: /refuse and sign out/i })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    fireEvent.click(screen.getByRole("button", { name: /^accept$/i }));
    expect(await screen.findByText("The portal")).toBeTruthy();
    expect(sent).toEqual([{ version: 2 }]);
  });
});
