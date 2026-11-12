import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { ImportBlocks } from "../../src/features/admin/arrival/ImportBlocks";
import {
  neededBy,
  type OfferedBlock,
  requested,
  toggled,
} from "../../src/features/admin/arrival/importBlocks";

// Issue 392 — the arrival wizard's « what to bring »: ticking a block ticks what it needs, unticking one
// unticks what needs it, every block ticked asks for the whole portal; the Admin's account always comes.

const BLOCKS: OfferedBlock[] = [
  { key: "settings", needs: [], counts: {} },
  { key: "members", needs: [], counts: { members: 12 } },
  { key: "services", needs: [], counts: { services: 3 } },
  { key: "media", needs: ["services"], counts: {} },
  { key: "statistics", needs: ["media"], counts: {} },
  { key: "gamification", needs: [], counts: { quests: 17 } },
  { key: "marketplace", needs: ["gamification"], counts: { products: 40 } },
];
const ALL = new Set(BLOCKS.map((b) => b.key));

describe("the blocks an archive brings", () => {
  it("ticks what a block needs and unticks what needs it", () => {
    expect([...toggled(BLOCKS, new Set(), "statistics", true)].sort()).toEqual([
      "media",
      "services",
      "statistics",
    ]);
    expect([...toggled(BLOCKS, ALL, "services", false)].sort()).toEqual([
      "gamification",
      "marketplace",
      "members",
      "settings",
    ]);
    expect(neededBy(BLOCKS, ALL, "gamification")).toEqual(["marketplace"]);
  });

  it("asks for the whole portal when everything is ticked, else for the blocks ticked", () => {
    expect(requested(BLOCKS, ALL)).toBeUndefined();
    expect(requested(BLOCKS, new Set(["marketplace", "gamification"]))).toEqual([
      "gamification",
      "marketplace",
    ]);
  });

  it("shows each block with what it holds, why it is needed and what becomes of the members", async () => {
    function Harness() {
      const [chosen, setChosen] = useState<Set<string>>(new Set(ALL));
      return <ImportBlocks blocks={BLOCKS} chosen={chosen} onChange={setChosen} />;
    }
    const { container } = render(<Harness />);
    const marketplace = screen.getByRole("checkbox", { name: /^Marketplace/ });
    const gamification = screen.getByRole("checkbox", { name: /^Gamification/ });
    expect(marketplace).toBeChecked();
    expect(screen.getByText(/The Admin's account always comes/)).toBeInTheDocument();

    fireEvent.click(gamification); // the marketplace needs it: both go
    expect(gamification).not.toBeChecked();
    expect(marketplace).not.toBeChecked();
    fireEvent.click(marketplace); // and come back together
    expect(gamification).toBeChecked();

    fireEvent.click(screen.getByRole("checkbox", { name: /^Members/ }));
    expect(screen.getByText(/Only the Admin's account comes/)).toBeInTheDocument();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
