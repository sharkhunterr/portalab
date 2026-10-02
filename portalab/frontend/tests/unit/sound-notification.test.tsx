import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PreferencesProvider } from "../../src/design-system/a11y/PreferencesProvider";
import { Notification, NotificationArea, useNotify } from "../../src/design-system/components/Notification";
import { SoundService } from "../../src/design-system/sound/SoundService";

// 022 T034 — sound off honoured; no autoplay before a gesture; reduced motion removes animation (tokens);
// severity meaning (icon + text) is unchanged by style or position.

describe("sound", () => {
  it("never plays before a user gesture, nor when disabled, nor unknown assets", async () => {
    const play = vi.fn(async () => undefined);
    const service = new SoundService(() => ({ play }));
    service.sounds = { notification: "asset:chime.ogg", alert: "https://evil/x.mp3" };
    expect(await service.play("notification")).toBe(false);
    service.noteGesture();
    expect(await service.play("notification")).toBe(true);
    expect(await service.play("alert")).toBe(false); // only bundled assets
    service.enabled = false;
    expect(await service.play("notification")).toBe(false);
    expect(play).toHaveBeenCalledTimes(1);
  });

  it("a failing asset fails silently", async () => {
    const service = new SoundService(() => ({ play: async () => Promise.reject(new Error("decode")) }));
    service.noteGesture();
    service.sounds = { success: "asset:ok.ogg" };
    expect(await service.play("success")).toBe(false);
  });
});

function Trigger() {
  const notify = useNotify();
  return (
    <button type="button" onClick={() => notify({ severity: "critical", title: "Backup failed" })}>
      fire
    </button>
  );
}

describe("notification appearance", () => {
  it.each([
    ["top-end", "toast"],
    ["bottom-start", "banner"],
  ] as const)("position %s / %s keeps severity meaning", (position, style) => {
    render(
      <PreferencesProvider initial={{ notificationPosition: position, notificationStyle: style }}>
        <NotificationArea>
          <Trigger />
        </NotificationArea>
      </PreferencesProvider>,
    );
    act(() => screen.getByText("fire").click());
    const region = screen.getByRole("region", { name: "Notifications" });
    expect(region).toHaveAttribute("data-position", position);
    const alert = screen
      .getAllByRole("alert")
      .find((el) => el.classList.contains("ds-notification")) as HTMLElement;
    expect(alert).toHaveTextContent("Critical");
    expect(alert).toHaveTextContent("Backup failed");
    expect(alert.querySelector("svg")).not.toBeNull();
  });

  it("renders a standalone notification with icon + text", () => {
    render(<Notification item={{ id: "1", severity: "warning", title: "Disk almost full" }} />);
    const notification = screen.getAllByRole("status").find((el) => el.classList.contains("ds-notification"));
    expect(notification).toHaveTextContent("Warning");
    expect(notification).toHaveTextContent("Disk almost full");
  });
});
