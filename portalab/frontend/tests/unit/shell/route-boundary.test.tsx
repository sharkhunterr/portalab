import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { RegionBoundary, RouteStateView, stateFor } from "../../../src/shell/router/RouteBoundary";
import { ApiError } from "../../../src/state/regions";

// 004 T020 — loading/error/unavailable/unauthorized/not-available; existence-sensitive routes render the
// same output for forbidden and missing; a failing region stays inside its boundary.

function Boom({ error }: { error: unknown }): never {
  throw error;
}

describe("route states", () => {
  it("maps errors to states, hiding existence where needed", () => {
    expect(stateFor(new ApiError(403, "x"), false)).toBe("unauthorized");
    expect(stateFor(new ApiError(403, "x"), true)).toBe("not-available");
    expect(stateFor(new ApiError(404, "x"), true)).toBe("not-available");
    expect(stateFor(new ApiError(503, "x"), false)).toBe("unavailable");
    expect(stateFor(new Error("chunk failed"), false)).toBe("error");
  });

  it("forbidden and missing look identical on existence-sensitive routes", () => {
    const forbidden = render(
      <MemoryRouter>
        <RegionBoundary existenceSensitive>
          <Boom error={new ApiError(403, "forbidden")} />
        </RegionBoundary>
      </MemoryRouter>,
    );
    const html = forbidden.container.innerHTML;
    forbidden.unmount();
    const missing = render(
      <MemoryRouter>
        <RegionBoundary existenceSensitive>
          <Boom error={new ApiError(404, "missing")} />
        </RegionBoundary>
      </MemoryRouter>,
    );
    expect(missing.container.innerHTML).toBe(html);
    expect(screen.getByText("This page is not available.")).toBeInTheDocument();
  });

  it("a failing region keeps the rest of the page alive and offers a retry", () => {
    render(
      <MemoryRouter>
        <nav aria-label="Main navigation">still here</nav>
        <RegionBoundary>
          <Boom error={new Error("render failure")} />
        </RegionBoundary>
      </MemoryRouter>,
    );
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toHaveTextContent("still here");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("clears the error when the user navigates to another page", () => {
    const view = render(
      <MemoryRouter>
        <RegionBoundary resetKey="/services/s1">
          <Boom error={new Error("render failure")} />
        </RegionBoundary>
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    view.rerender(
      <MemoryRouter>
        <RegionBoundary resetKey="/search">
          <p>Search page</p>
        </RegionBoundary>
      </MemoryRouter>,
    );
    expect(screen.getByText("Search page")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("renders every route state with a functional state", () => {
    for (const state of ["unauthorized", "unavailable", "error"] as const) {
      const { container, unmount } = render(
        <MemoryRouter>
          <RouteStateView state={state} />
        </MemoryRouter>,
      );
      expect(container.querySelector("[data-state]")).not.toBeNull();
      unmount();
    }
  });
});
