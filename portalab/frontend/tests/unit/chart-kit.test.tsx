import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { DonutChart, HeatmapChart } from "../../src/design-system/charts/Charts";
import {
  DumbbellChart,
  MirrorBars,
  PolarWheel,
  RingsChart,
  StackedProgress,
  WaffleChart,
} from "../../src/design-system/charts/Shapes";
import ChartGallery from "../../src/features/appearance/charts/ChartGallery";

// issue 117 — the chart kit: each shape says its values in words too (never colour alone), and the
// gallery draws every one of them.

describe("chart kit", () => {
  it("names the values of its drawn shapes", () => {
    render(
      <>
        <PolarWheel values={[1, 4, 2]} labels={["Mon", "Tue", "Wed"]} label="Week" />
        <RingsChart items={[{ label: "Films", value: 82 }]} />
        <StackedProgress label="Quota" total={10} items={[{ label: "Used", value: 4 }]} />
        <WaffleChart value={68} label="finished" />
        <MirrorBars
          left={{ label: "Me" }}
          right={{ label: "Others" }}
          rows={[{ label: "Action", left: 3, right: 5 }]}
        />
        <DumbbellChart before="Before" after="After" rows={[{ label: "Films", before: 2, after: 5 }]} />
        <DonutChart
          items={[
            { label: "Films", value: 3 },
            { label: "Series", value: 1 },
          ]}
          totalLabel="plays"
        />
        <HeatmapChart rows={["Mon"]} columns={["0h", "3h"]} values={[[1, 7]]} label="Habits" />
      </>,
    );
    expect(screen.getByRole("img", { name: "Week" }).querySelector("title")?.textContent).toBe("Mon : 1");
    expect(screen.getByText("82 %")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Quota" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "finished : 68 %" }).querySelectorAll("[data-on]")).toHaveLength(
      68,
    );
    expect(screen.getByText("Action")).toBeTruthy();
    expect(screen.getByText("75 %")).toBeTruthy(); // the donut's share of films
    expect(screen.getByRole("table").textContent).toContain("7"); // the heatmap as a table too
  });

  it("draws every shape in the gallery", () => {
    render(
      <MemoryRouter>
        <ChartGallery />
      </MemoryRouter>,
    );
    expect(document.querySelectorAll(".admin-section").length).toBeGreaterThanOrEqual(21);
  });
});
