import { render } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { CoinBadge, LevelBadge, ProgressBar } from "../../src/design-system/components/Badges";
import { ListItem, StatFigure, Tile, TileGrid } from "../../src/design-system/components/Collections";
import { Card } from "../../src/design-system/components/Content";
import { Icon } from "../../src/design-system/components/Icon";
import { PageHeader } from "../../src/design-system/components/PageHeader";
import { EmptyState, Skeleton } from "../../src/design-system/components/Placeholders";
import { BUILTIN_THEMES } from "../../src/design-system/themes/builtin";
import { ThemeProvider } from "../../src/design-system/themes/ThemeProvider";

// 027 T016 — the page kit has no axe violations under every built-in theme (contrast is checked by the
// floor tests and by Playwright in a real browser).

function Page() {
  return (
    <main>
      <PageHeader
        title="Support"
        icon="lifebuoy"
        context="We are here to help"
        primary={{ label: "New ticket" }}
      />
      <Card title="Progress" icon="trophy" level={2}>
        <LevelBadge level={4} label="Level 4" />
        <ProgressBar value={0.3} label="Level 4: 300 of 1000 XP" />
        <CoinBadge amount={120} label="Coins" />
      </Card>
      <TileGrid label="Recently added">
        <Tile key="a" title="Film" subtitle="2024" href="/media/1" />
        <Tile key="b" title="Series" onSelect={() => {}} />
      </TileGrid>
      <ul>
        <ListItem leading={<Icon name="ticket" />} title="Ticket #1" meta="Open" href="/support/tickets/1" />
      </ul>
      <StatFigure label="Requests" value={12} />
      <Skeleton shape="list" count={2} label="Loading tickets" />
      <EmptyState title="No feedback yet" action={{ label: "Give feedback", href: "/support/feedback" }} />
    </main>
  );
}

describe("page kit accessibility", () => {
  for (const theme of BUILTIN_THEMES) {
    it(`has no axe violations under ${theme.key}`, async () => {
      const { container } = render(
        <PreferencesProvider initial={{ theme: theme.key }}>
          <ThemeProvider>
            <Page />
          </ThemeProvider>
        </PreferencesProvider>,
      );
      const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
      expect(results.violations.map((v) => v.id)).toEqual([]);
    });
  }
});
