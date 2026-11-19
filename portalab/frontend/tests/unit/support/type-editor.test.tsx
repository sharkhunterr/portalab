import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// Issue 513 — renaming a ticket type saves only what a type takes (the row read back also carries its
// version and date, which the server refuses), and a refused request reads « field (reason) », never
// « [object Object] ».

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { Definitions } from "../../../src/features/support/admin/Definitions";
import { ApiError, problemErrors } from "../../../src/state/regions";
import { json } from "../../support/fake-api";

const MEDIA_TYPE = {
  key: "media_issue",
  label: "A problem with a media",
  workflow_key: "baseline",
  fields: [],
  enabled: true,
  media: true,
  public: false,
  version: 3,
  updated_at: "2026-11-19T17:00:00Z",
};

const sent: unknown[] = [];

function renderTypes() {
  sent.length = 0;
  fake.handler = async (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/admin/support/types") return json(200, [MEDIA_TYPE]);
    if (path === "/api/v1/admin/support/workflows")
      return json(200, [{ key: "baseline", version: 1, definition: {} }]);
    if (path === "/api/v1/admin/support/forms") return json(200, []);
    if (path === "/api/v1/admin/support/types/media_issue" && request.method === "PUT") {
      sent.push(await request.json());
      return json(200, { ...MEDIA_TYPE, label: "Problème Média", version: 4 });
    }
    return json(404, {});
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Definitions />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("a ticket type's editor", () => {
  it("renames a type sending only what a type takes", async () => {
    renderTypes();
    fireEvent.click(screen.getByRole("button", { name: "Ticket types" }));
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Type name"), { target: { value: "Problème Média" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({
      label: "Problème Média",
      workflow_key: "baseline",
      enabled: true,
      media: true,
      public: false,
      fields: [],
    });
  });

  it("reads a refused request's errors as text", () => {
    const refused = new ApiError(422, "The request is invalid.", "request.invalid", {
      errors: [{ loc: ["body", "updated_at"], type: "extra_forbidden" }, "A plain message"],
    });
    expect(problemErrors(refused)).toEqual(["updated_at (extra_forbidden)", "A plain message"]);
    expect(problemErrors(new Error("x"))).toEqual([]);
  });
});
