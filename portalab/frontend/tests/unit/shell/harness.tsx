import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, Outlet, type RouteObject, RouterProvider } from "react-router";
import { AnnounceProvider } from "../../../src/design-system/a11y/Announce";
import { AppShell } from "../../../src/shell/AppShell";
import { NavigationProvider, type NavigationView } from "../../../src/shell/nav/NavigationProvider";
import { RouteErrorElement } from "../../../src/shell/router/RouteBoundary";
import { type ShellSlots, ShellSlotsProvider } from "../../../src/shell/slots/providers";

/** Desktop viewport by default (``useBreakpoint`` reads matchMedia); tests may override it. */
export function setViewport(width: number): void {
  window.matchMedia = ((query: string) => {
    const min = Number(/min-width:\s*(\d+)px/.exec(query)?.[1] ?? 0);
    return {
      matches: width >= min,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    };
  }) as typeof window.matchMedia;
}

setViewport(1280);

export const VIEW: NavigationView = {
  version: "v1",
  degraded: false,
  groups: [
    {
      key: "main",
      label_key: "nav.group.main",
      entries: [
        { key: "shell.home", label_key: "nav.home", route: "/" },
        { key: "health.services", label_key: "nav.services", route: "/services" },
      ],
    },
    {
      key: "me",
      label_key: "nav.group.me",
      entries: [{ key: "identity.account", label_key: "nav.account", route: "/account" }],
    },
  ],
  commands: [
    { key: "health.services", label_key: "nav.services", route: "/services", kind: "navigate" },
    {
      key: "identity.account",
      label_key: "nav.account",
      route: "/account",
      kind: "navigate",
      keywords: ["profile"],
    },
    {
      key: "shell.shortcuts_help",
      label_key: "nav.shortcuts",
      kind: "action",
      action_id: "shell.show_shortcuts",
    },
  ],
  related: { "/services": [{ key: "x.manage", label_key: "nav.admin.services", route: "/admin/services" }] },
  crumbs: {},
};

export function renderShell(
  options: {
    path?: string;
    children?: RouteObject[];
    slots?: ShellSlots;
    extra?: ReactNode;
    shortcuts?: Record<string, string>;
  } = {},
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: (
          <AppShell userName="Alex" onSignOut={() => undefined} shortcutOverrides={options.shortcuts ?? {}} />
        ),
        errorElement: <RouteErrorElement />,
        handle: { crumb: "Home" },
        children: options.children ?? [
          { index: true, element: <h1>Home page</h1> },
          { path: "account", element: <h1>Account page</h1>, handle: { crumb: "Account" } },
          {
            path: "services",
            handle: { crumb: "Services" },
            element: <Outlet />,
            children: [
              { index: true, element: <h1>Services page</h1> },
              {
                path: ":serviceId",
                element: <h1>Service detail</h1>,
                handle: { crumb: (p: { serviceId?: string }) => `Service ${p.serviceId}` },
              },
            ],
          },
        ],
      },
    ],
    { initialEntries: [options.path ?? "/"] },
  );
  const result = render(
    <QueryClientProvider client={client}>
      <AnnounceProvider>
        <ShellSlotsProvider value={options.slots ?? {}}>
          <NavigationProvider live={false}>
            <RouterProvider router={router} />
            {options.extra}
          </NavigationProvider>
        </ShellSlotsProvider>
      </AnnounceProvider>
    </QueryClientProvider>,
  );
  return { ...result, router };
}
