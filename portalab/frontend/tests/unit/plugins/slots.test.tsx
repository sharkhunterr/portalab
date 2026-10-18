import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 030 T041 (US1b) — a plugin's slot: its button shows where Portalab places it (here a title's page), opens a
// modal Portalab draws from the plugin's blocks with the title as parameter; ticking a playlist posts it;
// nothing shows when no plugin adds to the place.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { PluginSlot } from "../../../src/features/plugins/slots/PluginSlot";
import { json } from "../../support/fake-api";

const SLOT = {
  id: "playlist:add",
  plugin: "playlist",
  slot: "media.actions",
  key: "add",
  label_key: "Add to a playlist",
  icon: "list-plus",
  opens: "add_to",
};
const SURFACE = {
  plugin: "playlist",
  key: "add_to",
  kind: "modal",
  title_key: "Add to a playlist",
  blocks: [{ kind: "checklist", title_key: "Your playlists", data: "lists", action: "toggle", columns: [] }],
};

function show(name: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter(
          [{ path: "/media/:id", element: <PluginSlot name={name} params={{ item: "m42" }} /> }],
          {
            initialEntries: ["/media/m42"],
          },
        )}
      />
    </QueryClientProvider>,
  );
}

describe("plugin slots", () => {
  it("opens the plugin's modal with the title and posts a ticked playlist", async () => {
    const toggles: unknown[] = [];
    let listed = "";
    fake.handler = async (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/plugins/slots") return json(200, [SLOT]);
      if (url.pathname === "/api/v1/plugins/playlist/surfaces/add_to") return json(200, SURFACE);
      if (url.pathname === "/api/v1/plugins/playlist/lists") {
        listed = url.search;
        return json(200, { state: "available", items: [{ id: 1, label: "Friday", checked: false }] });
      }
      if (url.pathname === "/api/v1/plugins/playlist/toggle") {
        toggles.push(await request.json());
        return json(200, { state: "available" });
      }
      return json(404, {});
    };
    show("media.actions");
    fireEvent.click(await screen.findByRole("button", { name: /add to a playlist/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(await within(dialog).findByLabelText("Friday"));
    await waitFor(() => expect(toggles).toEqual([{ item: "m42", id: 1, checked: true }]));
    expect(listed).toContain("item=m42");
  });

  it("shows nothing where no plugin adds", async () => {
    fake.handler = async () => json(200, [SLOT]);
    show("header.action");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole("button")).toBeNull();
  });
});
