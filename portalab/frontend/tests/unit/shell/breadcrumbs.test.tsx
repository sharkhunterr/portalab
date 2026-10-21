import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// 004 T029 — breadcrumbs from route handles (incl. labels resolved from params), ancestors navigable,
// current page marked; related links per page; empty states always offer a next action.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { EmptyState } from "../../../src/shell/breadcrumbs/Breadcrumbs";
import { json } from "../../support/fake-api";
import { renderShell, VIEW } from "./harness";

describe("orientation", () => {
  it("builds the trail from route handles", async () => {
    fake.handler = () => json(200, VIEW);
    renderShell({ path: "/services/plex-1" });
    const trail = await screen.findByRole("navigation", { name: "Breadcrumb" });
    expect(trail).toHaveTextContent("HomeServicesService plex-1"); // separators are CSS-only
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(screen.getByText("Service plex-1")).toHaveAttribute("aria-current", "page");
  });

  it("shows related links of the page", async () => {
    fake.handler = () => json(200, VIEW);
    renderShell({ path: "/services" });
    expect(await screen.findByRole("complementary", { name: "Related" })).toHaveTextContent("Services");
  });

  it("empty states require a next action", () => {
    render(
      <MemoryRouter>
        <EmptyState title="No services yet" nextAction={<a href="/admin/services">Add a service</a>} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Add a service" })).toBeInTheDocument();
  });
});
