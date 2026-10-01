import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { ApiError, DataRegion, stateForError } from "../../src/state/regions";

// T050 — two regions load independently; a failing region renders its own error state.

function withClient(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function Explode(): ReactNode {
  throw new Error("render crash");
}

describe("DataRegion", () => {
  it("renders a failing region's error while the other shows its data", async () => {
    render(
      withClient(
        <>
          <DataRegion label="Services" queryKey={["services"]} queryFn={async () => ["plex", "radarr"]}>
            {(items) => (
              <ul>
                {items.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            )}
          </DataRegion>
          <DataRegion
            label="News"
            queryKey={["news"]}
            queryFn={async () => {
              throw new ApiError(503, "down", "unavailable");
            }}
          >
            {() => <p>never</p>}
          </DataRegion>
        </>,
      ),
    );
    const services = screen.getByRole("region", { name: "Services" });
    const news = screen.getByRole("region", { name: "News" });
    expect(await within(services).findByText("radarr")).toBeInTheDocument();
    const state = await within(news).findByRole("status");
    expect(state).toHaveAttribute("data-state", "unavailable");
    expect(within(news).getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(within(news).queryByText("never")).not.toBeInTheDocument();
  });

  it("isolates a region whose rendering throws", async () => {
    const original = console.error;
    console.error = () => undefined;
    try {
      render(
        withClient(
          <>
            <DataRegion label="Broken" queryKey={["broken"]} queryFn={async () => 1}>
              {() => <Explode />}
            </DataRegion>
            <DataRegion label="Healthy" queryKey={["healthy"]} queryFn={async () => "ok"}>
              {(value) => <p>{value}</p>}
            </DataRegion>
          </>,
        ),
      );
      expect(
        await within(screen.getByRole("region", { name: "Healthy" })).findByText("ok"),
      ).toBeInTheDocument();
      const broken = await within(screen.getByRole("region", { name: "Broken" })).findByRole("alert");
      expect(broken).toHaveAttribute("data-state", "error");
    } finally {
      console.error = original;
    }
  });

  it("shows loading first and no-data for empty results", async () => {
    render(
      withClient(
        <DataRegion
          label="Empty"
          queryKey={["empty"]}
          queryFn={async () => [] as string[]}
          isEmpty={(rows) => rows.length === 0}
        >
          {() => <p>rows</p>}
        </DataRegion>,
      ),
    );
    const region = screen.getByRole("region", { name: "Empty" });
    expect(within(region).getByRole("status")).toHaveAttribute("data-state", "loading");
    expect(await within(region).findByText("No data yet")).toBeInTheDocument();
  });

  it("maps API errors to functional states", () => {
    expect(stateForError(new ApiError(401, "x"))).toBe("unauthorized");
    expect(stateForError(new ApiError(403, "x"))).toBe("unauthorized");
    expect(stateForError(new ApiError(503, "x", "maintenance.window"))).toBe("maintenance");
    expect(stateForError(new ApiError(504, "x"))).toBe("unavailable");
    expect(stateForError(new Error("boom"))).toBe("error");
  });
});
