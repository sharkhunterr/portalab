import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 027 (#25) — « my tickets »: « new ticket » sits in the widget's header and opens the ticket form in a
// dialog; once sent, the dialog closes, the widget says so with a link to the new ticket. With no ticket
// yet, the widget still offers it.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { HeaderSlot } from "../../../src/features/dashboard/frame/actions";
import "../../../src/features/support/tickets/widget";
import { widgetComponent } from "../../../src/features/dashboard/widgets/registry";
import { json } from "../../support/fake-api";

function Framed({ data }: { data: unknown }) {
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const Widget = widgetComponent("support.my_tickets") as NonNullable<ReturnType<typeof widgetComponent>>;
  return (
    <section>
      <header>
        <span data-testid="slot" ref={setSlot} />
      </header>
      <HeaderSlot.Provider value={slot}>
        <Widget payload={{ state: "available", data } as never} config={{}} />
      </HeaderSlot.Provider>
    </section>
  );
}

function show(data: unknown) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createMemoryRouter([{ path: "/", element: <Framed data={data} /> }])} />
    </QueryClientProvider>,
  );
}

describe("my tickets widget", () => {
  it("opens a ticket from the dashboard, in a dialog", async () => {
    const sent: unknown[] = [];
    fake.handler = async (request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/tickets/types")) return json(200, [{ key: "access", label: "Access", fields: [] }]);
      if (path.endsWith("/services/health"))
        return json(200, {
          items: [
            { id: "svc-plex", name: "Plex", connector: "plex", state: "degraded" },
            { id: "svc-book", name: "Grimmory", connector: "grimmory", state: "operational" },
          ],
        });
      if (path.endsWith("/tickets") && request.method === "POST") {
        sent.push(await request.json());
        return json(201, { id: "t-42" });
      }
      return json(200, {});
    };
    show({ items: [] });
    expect(screen.getByText("No open ticket — all is well.")).toBeTruthy();
    const button = await screen.findByRole("button", { name: /New ticket/ });
    expect(screen.getByTestId("slot").contains(button)).toBe(true); // in the header
    fireEvent.click(button);
    const dialog = await screen.findByRole("dialog", { name: "Open a ticket" });
    expect(dialog).toBeTruthy();
    await screen.findByRole("option", { name: "Access" });
    fireEvent.change(screen.getByLabelText(/Kind of request/), { target: { value: "access" } });
    fireEvent.change(screen.getByLabelText(/^Title/), { target: { value: "Plex is down" } });
    // #27: the service is picked among the public ones, as buttons (with its state when not fine)
    const plex = await screen.findByRole("radio", { name: /Plex/ });
    expect(plex.closest("label")?.textContent).toContain("Degraded");
    fireEvent.click(plex);
    fireEvent.click(screen.getByRole("button", { name: "Open the ticket" }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatchObject({ type_key: "access", title: "Plex is down", service_id: "svc-plex" });
    expect(await screen.findByText(/Your ticket is open/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "See it" }).getAttribute("href")).toBe("/support/tickets/t-42");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
