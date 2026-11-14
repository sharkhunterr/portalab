import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

// Issue 429 follow-up — the avatar menu says « My progression » once, even when the navigation also
// contributes an entry going there.

vi.mock("../../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../../support/fake-api");
  installFakeApi();
  return importOriginal();
});

import { PersonalMenu } from "../../../src/shell/header/PersonalMenu";

describe("the avatar menu", () => {
  it("lists the progression once", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <PersonalMenu
            name="Jérémie"
            userId="u1"
            entries={[
              {
                key: "shell.progression",
                label_key: "nav.progression",
                icon: "trophy",
                route: "/progression",
              },
              {
                key: "shell.achievements",
                label_key: "nav.achievements",
                icon: "trophy",
                route: "/community/achievements",
              },
            ]}
            onNavigate={() => undefined}
            onSignOut={() => undefined}
          />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.pointerDown(screen.getByRole("button", { name: /Jérémie/ }), { button: 0, ctrlKey: false });
    const items = (await screen.findAllByRole("menuitem")).map((i) => i.textContent);
    expect(items.filter((label) => /progression/i.test(label ?? ""))).toHaveLength(1);
  });
});
