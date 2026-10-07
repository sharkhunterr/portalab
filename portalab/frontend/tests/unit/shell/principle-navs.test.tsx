import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import type { NavSection } from "../../../src/shell/nav/NavigationProvider";
import { DockNav, LauncherNav, ReelNav, TabsNav, TerminalNav } from "../../../src/shell/nav/PrincipleNavs";

// 027 — navigation principles themes may choose: a dock, book tabs, a launcher screen, a terminal line and a
// film reel.
// Same destinations as every variant: a member hub opens on its first page, Administration lists its topics,
// the current section is marked, Escape closes an open list.

const SECTIONS: NavSection[] = [
  {
    key: "home",
    label_key: "nav.section.home",
    icon: "home",
    audience: "everyone",
    direct: true,
    topics: [],
    entries: [{ key: "shell.home", label_key: "nav.home", route: "/" }],
  },
  {
    key: "media",
    label_key: "nav.section.media",
    icon: "film",
    audience: "everyone",
    direct: false,
    topics: [],
    entries: [
      { key: "media.home", label_key: "nav.media", route: "/media" },
      { key: "media.requests", label_key: "nav.media_requests", route: "/media/requests" },
    ],
  },
  {
    key: "admin",
    label_key: "nav.section.admin",
    icon: "shield",
    audience: "administration",
    direct: false,
    entries: [],
    topics: [
      {
        key: "hub.pilot",
        label_key: "nav.hub.pilot",
        route: "/admin",
        entries: [{ key: "admin.center", label_key: "nav.admin.control_center", route: "/admin" }],
      },
      {
        key: "hub.services",
        label_key: "nav.hub.services",
        route: "/admin/services",
        entries: [{ key: "admin.services", label_key: "nav.admin.services", route: "/admin/services" }],
      },
    ],
  },
];

function show(element: ReactNode, at = "/media/requests") {
  render(<RouterProvider router={createMemoryRouter([{ path: "*", element }], { initialEntries: [at] })} />);
}

describe("navigation principles", () => {
  it("dock: hubs are links, Administration opens its topics above the dock", () => {
    show(<DockNav sections={SECTIONS} />);
    const nav = screen.getByRole("navigation");
    const media = within(nav).getByRole("link", { name: /media/i });
    expect(media.getAttribute("href")).toBe("/media");
    expect(media.getAttribute("data-active")).toBe("true");
    const admin = within(nav).getByRole("button", { name: /admin/i });
    fireEvent.click(admin);
    expect(admin.getAttribute("aria-expanded")).toBe("true");
    expect(
      within(nav)
        .getAllByRole("link")
        .map((a) => a.getAttribute("href")),
    ).toContain("/admin/services");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(admin.getAttribute("aria-expanded")).toBe("false");
  });

  it("tabs: one bookmark per section, the current one marked", () => {
    show(<TabsNav sections={SECTIONS} />);
    const links = screen.getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/", "/media"]);
    expect(links[1]?.getAttribute("aria-current")).toBe("page");
  });

  it("launcher: a start button opens every section as a tile with its pages", () => {
    show(<LauncherNav sections={SECTIONS} />);
    fireEvent.click(screen.getByRole("button", { name: /menu/i }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getAllByRole("listitem").length).toBeGreaterThanOrEqual(3);
    expect(
      within(dialog)
        .getAllByRole("link")
        .map((a) => a.getAttribute("href")),
    ).toContain("/media/requests");
  });

  it("terminal: sections as commands, the current section's pages below", () => {
    show(<TerminalNav sections={SECTIONS} />);
    const lists = screen.getAllByRole("list");
    expect(lists).toHaveLength(2);
    const current = within(lists[1] as HTMLElement).getByRole("link", { current: "page" });
    expect(current.getAttribute("href")).toBe("/media/requests");
  });

  it("reel: one frame per section, the current one lit, Administration unrolls its topics", () => {
    show(<ReelNav sections={SECTIONS} />);
    const nav = screen.getByRole("navigation");
    const media = within(nav).getByRole("link", { name: /media/i });
    expect(media.getAttribute("data-active")).toBe("true");
    const admin = within(nav).getByRole("button", { name: /admin/i });
    fireEvent.click(admin);
    expect(admin.getAttribute("aria-expanded")).toBe("true");
    expect(
      within(nav)
        .getAllByRole("link")
        .map((a) => a.getAttribute("href")),
    ).toContain("/admin/services");
  });
});
