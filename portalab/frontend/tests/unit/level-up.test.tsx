import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { LevelBadge, levelTier } from "../../src/design-system/components/Badges";
import { LevelUpMoment, showLevelUp } from "../../src/features/gamification/levelup/LevelUpMoment";

// 027 — the level badge changes rank every ten levels (legend from 100, mythic from 250) and wears a
// forced look when asked; the level-up moment shows the new level, what it brought and what it unlocked,
// in the chosen look, and waits to be closed.

describe("level badge ranks", () => {
  it("climbs a rank every ten levels", () => {
    expect([1, 9, 10, 25, 61, 99, 100, 249, 250, 999].map(levelTier)).toEqual([1, 1, 2, 3, 7, 7, 8, 8, 9, 9]);
    render(<LevelBadge level={120} label="Level 120" look="kapow" />);
    const badge = screen.getByRole("img", { name: "Level 120" });
    expect(badge.getAttribute("data-tier")).toBe("8");
    expect(badge.getAttribute("data-look")).toBe("kapow");
  });
});

describe("level-up moment", () => {
  it("shows the new level, its gains and unlocks, then closes", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <PreferencesProvider>
            <LevelUpMoment />
          </PreferencesProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    await act(async () => showLevelUp({ level: 12, preview: "comic" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.getAttribute("data-look")).toBe("comic");
    expect(within(dialog).getByText(/12/, { selector: "h2" })).toBeTruthy();
    expect(within(dialog).getByText("Living legend")).toBeTruthy(); // an achievement unlocked
    expect(within(dialog).getByText("Crowned level badge")).toBeTruthy(); // what it unlocked
    expect(within(dialog).getByText(/\+350/)).toBeTruthy(); // 100 + 250 Coins
    fireEvent.click(within(dialog).getByRole("button", { name: /continue/i }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
