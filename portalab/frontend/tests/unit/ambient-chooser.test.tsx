import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PreferencesProvider, usePreferences } from "../../src/design-system/a11y/PreferencesProvider";
import { AmbientChooser } from "../../src/features/appearance/AmbientChooser";

// #71 — the ambiences as a plain list: nothing animated in it, the rarest first with their rarity shown,
// « Preview » opens a window that plays it, « Apply » wears it at once (from the list or the window).

function Current() {
  const { preferences } = usePreferences();
  return <output data-testid="current">{preferences.ambient}</output>;
}

function setup() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PreferencesProvider initial={{ ambient: "theme" }}>
        <AmbientChooser
          themeAmbient="snow"
          choices={[
            { key: "snow", locked: false },
            { key: "lavalamp", locked: false, rarity: "legendary", price: 1500 },
            { key: "bokeh", locked: false, rarity: "rare", price: 450 },
            { key: "inferno", locked: true, rarity: "legendary", price: 1500 },
          ]}
        />
        <Current />
      </PreferencesProvider>
    </QueryClientProvider>,
  );
}

describe("ambient chooser", () => {
  it("lists what the member owns, rarest first, without any animation running", () => {
    setup();
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((row) => row.getAttribute("data-rarity"))).toEqual([
      "theme",
      "legendary",
      "rare",
      "free",
    ]);
    expect(within(rows[1] as HTMLElement).getByText(/legendary/i)).toBeInTheDocument();
    expect(document.querySelectorAll(".ambient, canvas")).toHaveLength(0); // no live preview in the list
    expect(screen.queryByText(/inferno/i)).toBeNull(); // locked: in the shop, not here
  });

  it("filters by rarity", () => {
    setup();
    fireEvent.click(within(screen.getByRole("group")).getByRole("button", { name: /^rare/i }));
    expect(screen.getAllByRole("listitem").map((row) => row.getAttribute("data-rarity"))).toEqual(["rare"]);
  });

  it("applies from the list and from the preview window", () => {
    setup();
    const legendary = screen.getAllByRole("listitem")[1] as HTMLElement;
    fireEvent.click(within(legendary).getByRole("button", { name: /apply/i }));
    expect(screen.getByTestId("current")).toHaveTextContent("lavalamp");

    const rare = screen.getAllByRole("listitem")[2] as HTMLElement;
    fireEvent.click(within(rare).getByRole("button", { name: /preview/i }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getAllByText(/rare/i).length).toBeGreaterThan(0);
    expect(dialog.querySelector(".ambient-detail__stage")).not.toBeNull(); // it plays in the window
    fireEvent.click(within(dialog).getByRole("button", { name: /^apply$/i }));
    expect(screen.getByTestId("current")).toHaveTextContent("bokeh");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
