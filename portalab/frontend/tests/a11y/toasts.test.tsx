import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// 010 T018 — live toasts: an alert is announced assertively (role=alert), a notification politely
// (role=status); a critical alert stays until acknowledged; presentation preferences change appearance
// only; sound-off silences the cue (a critical alert never overrides it); keyboard dismissal works.

const fake = vi.hoisted(() => ({
  handler: (_: Request): Response | Promise<Response> => new Response(null),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const { installFakeApi } = await import("../support/fake-api");
  const installed = installFakeApi();
  Object.defineProperty(installed, "handler", { get: () => fake.handler });
  return importOriginal();
});

import type { LiveEvent, StreamOptions } from "../../src/api/stream";
import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { NotificationArea } from "../../src/design-system/components/Notification";
import { sound } from "../../src/design-system/sound/SoundService";
import { ToastRegion } from "../../src/features/notifications/toasts/ToastRegion";
import { json } from "../support/fake-api";

const ITEMS = [
  { id: "a", kind: "alert", priority: "critical", title: "Media is down", body: "" },
  { id: "n", kind: "notification", priority: "normal", title: "New film", body: "Dune" },
].map((i) => ({
  ...i,
  category: "x.y",
  count: 1,
  action_url: null,
  read: false,
  archived: false,
  created_at: "2026-10-03T10:00:00Z",
  updated_at: "2026-10-03T10:00:00Z",
}));

function setup(preferences: Record<string, unknown> = {}) {
  let emit: (event: LiveEvent) => void = () => undefined;
  const connect = (options: StreamOptions) => {
    emit = options.onEvent;
    return { close: () => undefined };
  };
  fake.handler = () => json(200, { items: ITEMS, next_cursor: null, unread: 2 });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PreferencesProvider initial={{ notificationDurationSeconds: 1, ...preferences }}>
        <NotificationArea>
          <ToastRegion connect={connect} />
        </NotificationArea>
      </PreferencesProvider>
    </QueryClientProvider>,
  );
  return (id: string) => act(() => emit({ id: "1", topic: "notification.created", data: { id } }));
}

async function toast(title: string): Promise<HTMLElement> {
  return (await screen.findByText(title)).closest(".ds-notification") as HTMLElement;
}

describe("live toasts", () => {
  it("alerts are assertive and persist; notifications are polite and expire", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const ping = setup({ notificationPosition: "bottom-start", notificationStyle: "banner" });
    ping("a");
    ping("n");
    ping("n"); // the same ping twice shows one toast
    const alert = await toast("Media is down");
    expect(alert.getAttribute("role")).toBe("alert");
    expect(alert.textContent).toContain("Critical");
    const notification = await toast("New film");
    expect(notification.getAttribute("role")).toBe("status");
    expect(screen.getAllByText("New film").length).toBe(1);
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    await act(async () => {
      vi.advanceTimersByTime(600); // 027: it plays its exit animation, then goes
    });
    expect(screen.queryByText("New film")).toBeNull();
    expect(screen.getByText("Media is down")).toBeTruthy(); // critical stays until acknowledged
    const dismiss = screen.getByRole("button", { name: "Dismiss: Media is down" });
    dismiss.focus();
    fireEvent.click(dismiss);
    expect(screen.getByText("Media is down").closest(".ds-notification")?.hasAttribute("data-leaving")).toBe(
      true,
    );
    await act(async () => {
      vi.advanceTimersByTime(600);
    });
    expect(screen.queryByText("Media is down")).toBeNull();
    vi.useRealTimers();
  });

  it("sound-off silences even a critical alert", async () => {
    const play = vi.spyOn(sound, "play");
    const ping = setup({ soundEnabled: false });
    ping("a");
    await toast("Media is down");
    expect(sound.enabled).toBe(false);
    expect(await play.mock.results[0]?.value).toBe(false);
  });
});
