import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

// 027 — a profile opens on the member's banner and framed avatar; on one's own profile « Customise » lists
// the banners and frames, those sold and not owned locked with a way to the shop, and the film backdrop
// locked until bought.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
  puts: [] as unknown[],
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { ProfilePage } from "../../../src/features/community/profile/ProfilePage";
import { json } from "../../support/fake-api";

const MEMBER = "01900000-0000-7000-8000-000000000042";

function show(viewer: string) {
  fake.handler = async (request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/me") return json(200, { id: viewer, display_name: "Ursula", has_avatar: false });
    if (path === "/api/v1/me/profile-looks" && request.method === "PUT") {
      fake.puts.push(await request.json());
      return json(200, { equipped: { banner: "aurora" } });
    }
    if (path === "/api/v1/me/profile-looks") {
      return json(200, {
        banners: [
          { key: "aurora", locked: false },
          { key: "synthwave", locked: true },
        ],
        frames: [
          { key: "none", locked: false },
          { key: "gold", locked: true },
        ],
        backdrop: { unlocked: false },
        equipped: { banner: "dusk", frame: "neon" },
      });
    }
    return json(200, {
      id: MEMBER,
      display_name: "Ursula",
      sections: [],
      looks: { banner: "dusk", frame: "neon" },
    });
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { container } = render(
    <QueryClientProvider client={client}>
      <RouterProvider
        router={createMemoryRouter([{ path: "/m/:memberId", element: <ProfilePage /> }], {
          initialEntries: [`/m/${MEMBER}`],
        })}
      />
    </QueryClientProvider>,
  );
  return container;
}

describe("profile looks", () => {
  it("shows the banner and frame, customisable on one's own profile", async () => {
    const container = show(MEMBER);
    expect(await screen.findByRole("heading", { level: 1, name: "Ursula" })).toBeTruthy();
    expect(container.querySelector(".profile-hero .profile-banner")?.getAttribute("data-banner")).toBe(
      "dusk",
    );
    expect(container.querySelector(".profile-hero .avatar-frame")?.getAttribute("data-frame")).toBe("neon");
    fireEvent.click(await screen.findByRole("button", { name: "Customise" }));
    const dialog = await screen.findByRole("dialog");
    const synthwave = await within(dialog).findByRole("button", { name: /Synthwave/ });
    expect((synthwave as HTMLButtonElement).disabled).toBe(true);
    expect(within(dialog).getAllByRole("link", { name: "In the shop" }).length).toBe(1);
    fireEvent.click(within(dialog).getByRole("button", { name: /Aurora/ }));
    await vi.waitFor(() => expect(fake.puts).toEqual([{ slot: "banner", value: "aurora" }]));
    fireEvent.click(within(dialog).getByRole("button", { name: "Film backdrop" }));
    expect(await within(dialog).findByText("Film backdrop locked")).toBeTruthy();
  });

  it("offers no customisation on someone else's profile", async () => {
    show("01900000-0000-7000-8000-000000000099");
    expect(await screen.findByRole("heading", { level: 1, name: "Ursula" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Customise" })).toBeNull();
  });
});
