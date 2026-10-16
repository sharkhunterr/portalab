import { act, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { normaliseElement } from "../../../src/design-system/visuals/registry";
import type { NavSection } from "../../../src/shell/nav/NavigationProvider";
import { PackNav, packNavLayout } from "../../../src/shell/nav/PackNav";

// 028 T064 (US4) — a pack's navigation: it may only open a key it was given (an address or an unknown key does
// nothing), a few times a second at most; it expands only when its place says it may; the landmark and its
// name stay Portalab's.

const SECTIONS: NavSection[] = [
  {
    key: "media",
    label_key: "nav.media",
    audience: "everyone",
    direct: false,
    topics: [],
    entries: [
      { key: "media.catalog", label_key: "nav.catalog", route: "/media" },
      { key: "media.requests", label_key: "nav.requests", route: "/media/requests" },
    ],
  },
];

// a desktop (``matchMedia`` is not in jsdom)
window.matchMedia = ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: () => undefined,
  removeEventListener: () => undefined,
  addListener: () => undefined,
  removeListener: () => undefined,
  dispatchEvent: () => false,
})) as typeof window.matchMedia;

afterEach(() => {
  vi.unstubAllGlobals();
});

function show(nav: Record<string, unknown> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("export default () => {}", { status: 200 })),
  );
  const element = normaliseElement({
    pack: "abysses",
    type: "navigation",
    look: "sonar",
    kind: "js",
    file: "/x/sha/nav-sonar/nav.js",
    nav: { position: "bottom", size: 64, ...nav } as never,
  });
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <PackNav
            element={element}
            sections={SECTIONS}
            unread={0}
            level={3}
            coins={10}
            onFail={() => undefined}
          />
        ),
      },
    ],
    { initialEntries: ["/"] },
  );
  render(<RouterProvider router={router} />);
  const frame = document.querySelector("iframe.pack-nav__frame") as HTMLIFrameElement;
  const target = frame.contentWindow as Window;
  target.postMessage = (() => undefined) as Window["postMessage"];
  const send = (data: Record<string, unknown>) =>
    act(() => {
      window.dispatchEvent(new MessageEvent("message", { source: target, data }));
    });
  return { router, send };
}

describe("pack navigation", () => {
  it("keeps its place within bounds", () => {
    const base = { pack: "p", type: "navigation" };
    expect(packNavLayout(normaliseElement({ ...base, nav: { size: 5000 } as never })).size).toBe(320);
    expect(packNavLayout(normaliseElement({ ...base, nav: { size: 2 } as never })).size).toBe(40);
    expect(packNavLayout(normaliseElement(base))).toEqual({ position: "bottom", size: 72, expands: false });
  });

  it("opens only a key it was given, a few times a second at most", async () => {
    const { router, send } = show();
    const pause = () => new Promise((resolve) => setTimeout(resolve, 420));
    // every ask counts toward the pace, a refused one too
    await send({ type: "navigate", key: "/admin/system" }); // an address: nothing
    await pause();
    await send({ type: "navigate", key: "admin.system" }); // a key it was not given: nothing
    expect(router.state.location.pathname).toBe("/");
    await pause();
    await send({ type: "navigate", key: "media.requests" });
    expect(router.state.location.pathname).toBe("/media/requests");
    await send({ type: "navigate", key: "media.catalog" }); // too soon after the last one
    expect(router.state.location.pathname).toBe("/media/requests");
    await pause();
    await send({ type: "navigate", key: "media" }); // a section: its first page
    expect(router.state.location.pathname).toBe("/media");
  });

  it("expands only when its place says it may, and the landmark stays Portalab's", async () => {
    const closed = show({ expands: false });
    await closed.send({ type: "expand", open: true });
    const nav = screen.getByRole("navigation");
    expect(nav).not.toHaveAttribute("data-expanded");
    expect(nav).toHaveAttribute("aria-label");
    expect(nav).toHaveAttribute("data-position", "bottom");
  });

  it("may cover the screen while open when it says it expands", async () => {
    const { send } = show({ expands: true });
    await send({ type: "expand", open: true });
    expect(screen.getByRole("navigation")).toHaveAttribute("data-expanded", "true");
    await send({ type: "expand", open: false });
    expect(screen.getByRole("navigation")).not.toHaveAttribute("data-expanded");
  });
});
