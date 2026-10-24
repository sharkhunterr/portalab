import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { SettingsHome, SettingsLayout } from "../../../src/features/settings/SettingsLayout";

// issue 14 — « My settings »: one place, the pages by intent, a search through every setting

function hub(path = "/settings") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<SettingsLayout />}>
          <Route path="settings" element={<SettingsHome />} />
          <Route path="account" element={<p>profile page</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("settings hub", () => {
  it("lists every page by intent, Play among them", () => {
    hub();
    for (const name of ["Profile", "Appearance", "Language & region", "Notifications", "Privacy", "Play"]) {
      expect(screen.getAllByRole("link", { name: new RegExp(name) }).length).toBeGreaterThan(0);
    }
  });

  it("finds a setting by a word near it, and leads to its page", () => {
    hub();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "dark" } });
    const results = screen.getByRole("list", { name: /1 result/ });
    const found = within(results).getByRole("link", { name: /Light or dark/ });
    expect(found).toHaveAttribute("href", "/settings/appearance");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "zzz" } });
    expect(screen.getByText("No setting matches.")).toBeInTheDocument();
  });

  it("a page keeps a way back to the list", () => {
    hub("/account");
    expect(screen.getByText("profile page")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /My settings/ }).length).toBeGreaterThan(0);
  });
});
