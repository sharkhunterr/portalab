import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnnounceProvider } from "../../src/design-system/a11y/Announce";
import { Avatar, hueOf, initialsOf } from "../../src/design-system/components/Avatar";
import {
  CoinBadge,
  compactNumber,
  LevelBadge,
  levelProgress,
  ProgressBar,
} from "../../src/design-system/components/Badges";
import { Icon } from "../../src/design-system/components/Icon";
import { EmptyState, Skeleton } from "../../src/design-system/components/Placeholders";
import {
  CelebrationProvider,
  CelebrationQueue,
  useCelebrate,
} from "../../src/design-system/feedback/Celebration";
import { SoundService } from "../../src/design-system/sound/SoundService";

// 027 T014–T019 — icon names, avatar fallback and stable hue, progression badges, skeleton/empty state
// contracts, celebration coalescing and reduced motion, extended sound events.

describe("Icon", () => {
  it("renders known names, a neutral dot for unknown ones, and is decorative without a label", () => {
    const { container } = render(
      <>
        <Icon name="trophy" />
        <Icon name="does-not-exist" />
        <Icon name="bell" label="Notifications" />
      </>,
    );
    const icons = container.querySelectorAll("svg");
    expect(icons[0]?.getAttribute("data-icon")).toBe("trophy");
    expect(icons[0]?.getAttribute("aria-hidden")).toBe("true");
    expect(icons[1]?.getAttribute("data-icon")).toBe("unknown");
    expect(screen.getByRole("img", { name: "Notifications" })).toBeTruthy();
  });
});

describe("Avatar", () => {
  it("falls back to initials with a hue stable per user, also when the image breaks", () => {
    expect(initialsOf("Ada Lovelace")).toBe("AL");
    expect(initialsOf("ursula")).toBe("U");
    expect(initialsOf("")).toBe("?");
    expect(hueOf("user-1")).toBe(hueOf("user-1"));
    expect(hueOf("user-1")).not.toBe(hueOf("user-2"));
    const { container } = render(<Avatar name="Ada Lovelace" userId="u1" src="/broken.png" />);
    const img = container.querySelector("img") as HTMLImageElement;
    act(() => {
      img.dispatchEvent(new Event("error"));
    });
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("img", { name: "Ada Lovelace" }).textContent).toBe("AL");
  });
});

describe("progression badges", () => {
  it("formats Coins compactly with the exact value in the accessible name", () => {
    expect(compactNumber(9999, "en")).toBe("9,999");
    expect(compactNumber(12450, "en")).toBe("12.5K");
    render(<CoinBadge amount={12450} label="Coins" locale="en" />);
    expect(screen.getByRole("img", { name: "Coins: 12,450" }).textContent).toBe("12.5K");
  });

  it("computes level progress and exposes it as a progressbar", () => {
    expect(levelProgress(240, 100, 400)).toBeCloseTo(0.4667, 3);
    expect(levelProgress(5000, 4000, null)).toBe(1);
    render(
      <>
        <LevelBadge level={3} label="Level 3" />
        <ProgressBar value={0.5} label="Level 3: 250 of 400 XP" />
      </>,
    );
    expect(screen.getByRole("img", { name: "Level 3" })).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: /Level 3/ }).getAttribute("aria-valuenow")).toBe("50");
  });
});

describe("placeholders", () => {
  it("skeletons mark the region busy; empty states always carry an action", () => {
    const onSelect = vi.fn();
    render(
      <>
        <Skeleton shape="tile" count={3} label="Loading media" />
        <EmptyState
          title="No tickets"
          message="Ask for help any time."
          action={{ label: "Open a ticket", onSelect }}
        />
      </>,
    );
    expect(screen.getByText("Loading media").closest("[aria-busy]")).toBeTruthy();
    screen.getByRole("button", { name: "Open a ticket" }).click();
    expect(onSelect).toHaveBeenCalled();
  });
});

describe("celebrations", () => {
  it("coalesces bursts: one playing, one pending, a waiting level-up wins", () => {
    const queue = new CelebrationQueue();
    queue.push({ kind: "reward", text: "+10 XP" });
    queue.push({ kind: "reward", text: "+20 XP" });
    queue.push({ kind: "level", text: "Level 4!" });
    queue.push({ kind: "reward", text: "+5 XP" });
    expect(queue.current?.text).toBe("+10 XP");
    expect(queue.next()?.text).toBe("Level 4!");
    expect(queue.next()).toBeNull();
  });

  it("shows the badge, announces it, and drops particles under reduced motion", () => {
    vi.useFakeTimers();
    document.documentElement.dataset.reducedMotion = "true";
    function Trigger() {
      const celebrate = useCelebrate();
      return (
        <button type="button" onClick={() => celebrate({ kind: "level", text: "Level 5!" })}>
          go
        </button>
      );
    }
    const { container } = render(
      <AnnounceProvider>
        <CelebrationProvider>
          <Trigger />
        </CelebrationProvider>
      </AnnounceProvider>,
    );
    act(() => screen.getByRole("button", { name: "go" }).click());
    expect(container.querySelector(".ds-celebration__badge")?.textContent).toBe("Level 5!");
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(container.querySelector(".ds-celebration")).toBeNull();
    vi.useRealTimers();
  });
});

describe("sound events", () => {
  it("plays reward and level-up sounds from the theme set after a gesture only", async () => {
    const played: string[] = [];
    const service = new SoundService((src) => ({ play: async () => void played.push(src) }));
    service.sounds = { reward: "asset:portalab/reward.wav", levelUp: "asset:portalab/level-up.wav" };
    expect(await service.play("reward")).toBe(false);
    service.noteGesture();
    expect(await service.play("levelUp")).toBe(true);
    expect(await service.play("ui")).toBe(false);
    expect(played).toEqual(["/assets/sounds/portalab/level-up.wav"]);
  });
});
